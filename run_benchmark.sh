#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 BENCHMARK_CPU SERVER_CPU [benchmark args...]"
    echo
    echo "Example:"
    echo "  $0 3 4"
    echo "  PYTHON=env314/bin/python $0 3 4 --help"
    echo
    echo "Environment:"
    echo "  SERVER=./build/src/ws_echo_server"
    echo "  HOST=127.0.0.1 TCP_PORT=9001 SSL_PORT=9002"
}

expand_cpu_list() {
    local list=${1//,/ }
    local item start end cpu

    for item in $list; do
        if [[ $item == *-* ]]; then
            start=${item%-*}
            end=${item#*-}
            for ((cpu = start; cpu <= end; cpu++)); do
                echo "$cpu"
            done
        else
            echo "$item"
        fi
    done
}

write_sysfs() {
    local value=$1
    local path=$2
    echo "$value" | sudo tee "$path" >/dev/null
}

port_is_open() {
    local port=$1
    (echo >"/dev/tcp/$HOST/$port") >/dev/null 2>&1
}

stop_server() {
    if [[ -n ${SERVER_PID:-} ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "Stopping websocket echo server..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}

restore() {
    local cpu dir governor min_freq max_freq

    stop_server

    if [[ ${#SAVED_CPUS[@]} -eq 0 ]]; then
        return
    fi

    echo "Restoring CPU frequency settings..."
    for cpu in "${SAVED_CPUS[@]}"; do
        dir="/sys/devices/system/cpu/cpu${cpu}/cpufreq"
        governor=${OLD_GOVERNOR[$cpu]}
        min_freq=${OLD_MIN_FREQ[$cpu]}
        max_freq=${OLD_MAX_FREQ[$cpu]}

        [[ -n $min_freq ]] && write_sysfs "$min_freq" "$dir/scaling_min_freq"
        [[ -n $max_freq ]] && write_sysfs "$max_freq" "$dir/scaling_max_freq"
        [[ -n $governor ]] && write_sysfs "$governor" "$dir/scaling_governor"
    done
}

add_policy_cpus() {
    local target_cpu=$1
    local cpufreq="/sys/devices/system/cpu/cpu${target_cpu}/cpufreq"
    local cpu

    if [[ ! -d $cpufreq ]]; then
        echo "CPU $target_cpu does not expose cpufreq controls at $cpufreq" >&2
        exit 1
    fi

    if [[ -r "$cpufreq/related_cpus" ]]; then
        while read -r cpu; do
            [[ -n ${SEEN[$cpu]:-} ]] && continue
            SEEN[$cpu]=1
            POLICY_CPUS+=("$cpu")
        done < <(expand_cpu_list "$(cat "$cpufreq/related_cpus")")
    else
        [[ -n ${SEEN[$target_cpu]:-} ]] && return
        SEEN[$target_cpu]=1
        POLICY_CPUS+=("$target_cpu")
    fi
}

wait_for_server() {
    local port=$1
    local attempt

    for attempt in {1..50}; do
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            echo "Server exited before port $port became ready" >&2
            wait "$SERVER_PID" || true
            exit 1
        fi

        if port_is_open "$port"; then
            return
        fi

        sleep 0.1
    done

    echo "Server did not start listening on $HOST:$port" >&2
    exit 1
}

if [[ $# -lt 2 || ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    usage
    exit 1
fi

CPU=$1
SERVER_CPU=$2
shift 2
PYTHON=${PYTHON:-python}
SERVER=${SERVER:-./build/src/ws_echo_server}
HOST=${HOST:-127.0.0.1}
TCP_PORT=${TCP_PORT:-9001}
SSL_PORT=${SSL_PORT:-9002}
SERVER_PID=

if [[ $CPU == "$SERVER_CPU" ]]; then
    echo "Benchmark CPU and server CPU must be different" >&2
    exit 1
fi

if [[ -r "/sys/devices/system/cpu/cpu${CPU}/topology/thread_siblings_list" ]]; then
    while read -r sibling; do
        if [[ $sibling == "$SERVER_CPU" ]]; then
            echo "Benchmark CPU $CPU and server CPU $SERVER_CPU share the same physical core" >&2
            exit 1
        fi
    done < <(expand_cpu_list "$(cat "/sys/devices/system/cpu/cpu${CPU}/topology/thread_siblings_list")")
fi

if [[ ! -x $SERVER ]]; then
    echo "Server executable not found or not executable: $SERVER" >&2
    exit 1
fi

if port_is_open "$TCP_PORT"; then
    echo "$HOST:$TCP_PORT is already in use; stop the existing server first" >&2
    exit 1
fi

if port_is_open "$SSL_PORT"; then
    echo "$HOST:$SSL_PORT is already in use; stop the existing server first" >&2
    exit 1
fi

declare -a POLICY_CPUS=()
declare -a SAVED_CPUS=()
declare -A SEEN=()
declare -A OLD_GOVERNOR=()
declare -A OLD_MIN_FREQ=()
declare -A OLD_MAX_FREQ=()

add_policy_cpus "$CPU"
add_policy_cpus "$SERVER_CPU"

trap restore EXIT INT TERM

echo "Selected benchmark logical CPU: $CPU"
if [[ -r "/sys/devices/system/cpu/cpu${CPU}/topology/thread_siblings_list" ]]; then
    echo "Benchmark SMT siblings: $(cat "/sys/devices/system/cpu/cpu${CPU}/topology/thread_siblings_list")"
fi
echo "Selected server logical CPU: $SERVER_CPU"
if [[ -r "/sys/devices/system/cpu/cpu${SERVER_CPU}/topology/thread_siblings_list" ]]; then
    echo "Server SMT siblings: $(cat "/sys/devices/system/cpu/cpu${SERVER_CPU}/topology/thread_siblings_list")"
fi
echo "Frequency policy CPUs: ${POLICY_CPUS[*]}"

for cpu in "${POLICY_CPUS[@]}"; do
    dir="/sys/devices/system/cpu/cpu${cpu}/cpufreq"
    [[ -d $dir ]] || continue

    OLD_GOVERNOR[$cpu]=$(cat "$dir/scaling_governor" 2>/dev/null || true)
    OLD_MIN_FREQ[$cpu]=$(cat "$dir/scaling_min_freq" 2>/dev/null || true)
    OLD_MAX_FREQ[$cpu]=$(cat "$dir/scaling_max_freq" 2>/dev/null || true)
    SAVED_CPUS+=("$cpu")
done

for cpu in "${SAVED_CPUS[@]}"; do
    dir="/sys/devices/system/cpu/cpu${cpu}/cpufreq"
    max_freq=$(cat "$dir/cpuinfo_max_freq")

    echo "Setting CPU $cpu to performance governor and max frequency $max_freq"
    write_sysfs performance "$dir/scaling_governor"
    write_sysfs "$max_freq" "$dir/scaling_max_freq"
    write_sysfs "$max_freq" "$dir/scaling_min_freq"
done

echo "Starting websocket echo server on logical CPU $SERVER_CPU..."
taskset -c "$SERVER_CPU" "$SERVER" "$HOST" "$TCP_PORT" "$SSL_PORT" &
SERVER_PID=$!
wait_for_server "$TCP_PORT"
wait_for_server "$SSL_PORT"

echo "Running benchmark on logical CPU $CPU..."
taskset -c "$CPU" "$PYTHON" -m wsbench.benchmark --host "$HOST" --tcp-port "$TCP_PORT" --ssl-port "$SSL_PORT" "$@"
