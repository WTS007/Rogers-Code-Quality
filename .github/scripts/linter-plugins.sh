#!/usr/bin/env bash
# =============================================================================
# Project Nexus — Linter Plugin Architecture (normalized LF)
# =============================================================================
# Modular linter runner with plugin registration mechanism.
# Runs specified linters and outputs results in unified JSON format.
#
# Usage:
#   ./linter-plugins.sh <linter_name>
#   ./linter-plugins.sh eslint
#   ./linter-plugins.sh bandit
#   ./linter-plugins.sh checkov
#   ./linter-plugins.sh --list          # List registered plugins
#
# Exit codes:
#   0 — Linter passed (warnings only or clean)
#   1 — Linter found errors
#   2 — Linter not found / configuration error
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# CONFIGURATION
# =============================================================================
STRICTNESS_LEVEL="${STRICTNESS_LEVEL:-medium}"
OUTPUT_DIR="${NEXUS_OUTPUT_DIR:-.}"
REPORT_FILE="${OUTPUT_DIR}/lint-report.json"

# =============================================================================
# PLUGIN REGISTRATION
# =============================================================================
# Register linters here. Map linter name → run command.
# Each plugin function must:
#   1. Install the tool if missing
#   2. Run the linter
#   3. Output unified JSON to stdout
#   4. Return 0 (warnings/clean) or 1 (errors)
# =============================================================================
declare -A PLUGINS=(
    ["eslint"]="run_eslint"
    ["bandit"]="run_bandit"
    ["checkov"]="run_checkov"
)

# To register a custom plugin, add to the PLUGINS array above:
#   PLUGINS["my_linter"]="run_my_linter"
# Then define the function run_my_linter() below.

# =============================================================================
# LOGGING
# =============================================================================
log_info()  { echo "[nexus:linter] ℹ️  $*" >&2; }
log_warn()  { echo "[nexus:linter] ⚠️  $*" >&2; }
log_error() { echo "[nexus:linter] ❌ $*" >&2; }
log_ok()    { echo "[nexus:linter] ✅ $*" >&2; }

# =============================================================================
# STRICTNESS THRESHOLDS
# =============================================================================
get_max_warnings() {
    case "${STRICTNESS_LEVEL}" in
        low)      echo 100 ;;
        medium)   echo 50  ;;
        high)     echo 10  ;;
        critical) echo 0   ;;
        *)        echo 50  ;;
    esac
}

get_max_errors() {
    case "${STRICTNESS_LEVEL}" in
        low)      echo 20 ;;
        medium)   echo 5  ;;
        high)     echo 1  ;;
        critical) echo 0  ;;
        *)        echo 5  ;;
    esac
}

# =============================================================================
# UNIFIED REPORT EMITTER
# =============================================================================
emit_unified_report() {
    local linter_name="$1"
    local status="$2"       # pass | warn | fail
    local warnings="$3"
    local errors="$4"
    local details="$5"      # JSON string of findings
    local duration="$6"

    cat <<JSONEOF
{
  "linter": "${linter_name}",
  "status": "${status}",
  "strictness_level": "${STRICTNESS_LEVEL}",
  "summary": {
    "warnings": ${warnings},
    "errors": ${errors},
    "max_warnings_allowed": $(get_max_warnings),
    "max_errors_allowed": $(get_max_errors)
  },
  "findings": ${details},
  "duration_seconds": ${duration},
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pipeline": "nexus-linter-plugins"
}
JSONEOF
}

# =============================================================================
# PLUGIN: ESLint
# =============================================================================
run_eslint() {
    log_info "Running ESLint..."

    # Ensure eslint is available
    if ! command -v npx &>/dev/null; then
        log_error "npx not found — Node.js is required for ESLint"
        emit_unified_report "eslint" "error" 0 0 "[]" 0
        return 2
    fi

    local start_time
    start_time=$(date +%s)

    # Determine config
    local eslint_config=""
    for cfg in .eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml .eslintrc.yaml eslint.config.js eslint.config.mjs; do
        if [[ -f "$cfg" ]]; then
            eslint_config="$cfg"
            break
        fi
    done

    # Run ESLint with JSON output
    local eslint_output exit_code=0
    eslint_output=$(npx eslint . \
        --format json \
        --no-error-on-unmatched-pattern \
        ${eslint_config:+--config "$eslint_config"} \
        2>/dev/null) || exit_code=$?

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Parse ESLint JSON output
    local warnings=0 errors=0
    if [[ -n "$eslint_output" ]]; then
        warnings=$(echo "$eslint_output" | jq '[.[].warningCount] | add // 0' 2>/dev/null || echo 0)
        errors=$(echo "$eslint_output" | jq '[.[].errorCount] | add // 0' 2>/dev/null || echo 0)
    fi

    # Build findings array
    local findings="[]"
    if [[ -n "$eslint_output" ]]; then
        findings=$(echo "$eslint_output" | jq '[.[] | select(.messages | length > 0) | {
            file: .filePath,
            messages: [.messages[] | {
                line: .line,
                column: .column,
                severity: (if .severity == 2 then "error" else "warning" end),
                rule: .ruleId,
                message: .message
            }]
        }]' 2>/dev/null || echo "[]")
    fi

    # Determine status
    local status="pass"
    local max_w max_e
    max_w=$(get_max_warnings)
    max_e=$(get_max_errors)

    if [[ "$errors" -gt "$max_e" ]]; then
        status="fail"
    elif [[ "$warnings" -gt "$max_w" ]]; then
        status="warn"
    fi

    emit_unified_report "eslint" "$status" "$warnings" "$errors" "$findings" "$duration"

    if [[ "$status" == "fail" ]]; then
        log_error "ESLint: ${errors} errors (max: ${max_e}), ${warnings} warnings"
        return 1
    else
        log_ok "ESLint: ${errors} errors, ${warnings} warnings — ${status}"
        return 0
    fi
}

# =============================================================================
# PLUGIN: Bandit (Python Security)
# =============================================================================
run_bandit() {
    log_info "Running Bandit..."

    # Ensure bandit is available
    if ! command -v bandit &>/dev/null; then
        log_info "Installing Bandit..."
        pip install bandit --quiet 2>/dev/null || {
            log_error "Failed to install Bandit"
            emit_unified_report "bandit" "error" 0 0 "[]" 0
            return 2
        }
    fi

    local start_time
    start_time=$(date +%s)

    # Determine severity level
    local severity_flag=""
    case "${STRICTNESS_LEVEL}" in
        low)      severity_flag="-ll" ;;   # medium and above
        medium)   severity_flag="-ll" ;;   # medium and above
        high)     severity_flag="-l"  ;;   # low and above (more findings)
        critical) severity_flag=""    ;;   # all severities
    esac

    # Run Bandit with JSON output
    local bandit_output exit_code=0
    bandit_output=$(bandit -r . \
        -f json \
        ${severity_flag} \
        --exclude './.venv,./venv,./node_modules,./.git' \
        2>/dev/null) || exit_code=$?

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Parse Bandit JSON output
    local warnings=0 errors=0
    if [[ -n "$bandit_output" ]]; then
        errors=$(echo "$bandit_output" | jq '.results | length' 2>/dev/null || echo 0)
        warnings=$(echo "$bandit_output" | jq '[.results[] | select(.issue_severity == "LOW")] | length' 2>/dev/null || echo 0)
        errors=$((errors - warnings))
    fi

    # Build findings array
    local findings="[]"
    if [[ -n "$bandit_output" ]]; then
        findings=$(echo "$bandit_output" | jq '[.results[] | {
            file: .filename,
            messages: [{
                line: .line_number,
                column: 0,
                severity: (.issue_severity | ascii_downcase),
                rule: .test_id,
                message: (.issue_text + " (Confidence: " + .issue_confidence + ")")
            }]
        }]' 2>/dev/null || echo "[]")
    fi

    # Determine status
    local status="pass"
    local max_w max_e
    max_w=$(get_max_warnings)
    max_e=$(get_max_errors)

    if [[ "$errors" -gt "$max_e" ]]; then
        status="fail"
    elif [[ "$warnings" -gt "$max_w" ]]; then
        status="warn"
    fi

    emit_unified_report "bandit" "$status" "$warnings" "$errors" "$findings" "$duration"

    if [[ "$status" == "fail" ]]; then
        log_error "Bandit: ${errors} issues (max: ${max_e}), ${warnings} low-severity"
        return 1
    else
        log_ok "Bandit: ${errors} issues, ${warnings} low-severity — ${status}"
        return 0
    fi
}

# =============================================================================
# PLUGIN: Checkov (Infrastructure as Code Security)
# =============================================================================
run_checkov() {
    log_info "Running Checkov..."

    # Ensure checkov is available
    if ! command -v checkov &>/dev/null; then
        log_info "Installing Checkov..."
        pip install checkov --quiet 2>/dev/null || {
            log_error "Failed to install Checkov"
            emit_unified_report "checkov" "error" 0 0 "[]" 0
            return 2
        }
    fi

    local start_time
    start_time=$(date +%s)

    # Determine check types based on available files
    local check_types=""
    [[ -d "terraform" ]] || [[ -n "$(find . -name '*.tf' -maxdepth 3 2>/dev/null | head -1)" ]] && check_types="terraform"
    [[ -f "Dockerfile" ]] || [[ -n "$(find . -name 'Dockerfile*' -maxdepth 3 2>/dev/null | head -1)" ]] && check_types="${check_types:+$check_types,}dockerfile"
    [[ -f "docker-compose.yml" ]] || [[ -f "docker-compose.yaml" ]] && check_types="${check_types:+$check_types,}docker_compose"
    [[ -d ".github" ]] && check_types="${check_types:+$check_types,}github_actions"
    [[ -n "$(find . -name '*.yaml' -o -name '*.yml' -maxdepth 3 2>/dev/null | head -1)" ]] && check_types="${check_types:+$check_types,}kubernetes"

    # Default to all if nothing specific detected
    if [[ -z "$check_types" ]]; then
        check_types="all"
    fi

    # Compact flag for strictness
    local compact_flag=""
    case "${STRICTNESS_LEVEL}" in
        low|medium) compact_flag="--compact" ;;
    esac

    # Run Checkov with JSON output
    local checkov_output exit_code=0
    checkov_output=$(checkov -d . \
        --output json \
        --quiet \
        ${compact_flag} \
        2>/dev/null) || exit_code=$?

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Parse Checkov JSON output
    local warnings=0 errors=0
    if [[ -n "$checkov_output" ]]; then
        # Checkov can output an array of check types or a single object
        local passed failed
        passed=$(echo "$checkov_output" | jq '[if type == "array" then .[] else . end | .summary.passed // 0] | add' 2>/dev/null || echo 0)
        failed=$(echo "$checkov_output" | jq '[if type == "array" then .[] else . end | .summary.failed // 0] | add' 2>/dev/null || echo 0)
        errors=$failed
    fi

    # Build findings array
    local findings="[]"
    if [[ -n "$checkov_output" ]]; then
        findings=$(echo "$checkov_output" | jq '[
            if type == "array" then .[] else . end |
            .results.failed_checks // [] | .[] | {
                file: .file_path,
                messages: [{
                    line: (.file_line_range[0] // 0),
                    column: 0,
                    severity: "error",
                    rule: .check_id,
                    message: (.check_name + " (" + .guideline + ")")
                }]
            }
        ]' 2>/dev/null || echo "[]")
    fi

    # Determine status
    local status="pass"
    local max_e
    max_e=$(get_max_errors)

    if [[ "$errors" -gt "$max_e" ]]; then
        status="fail"
    elif [[ "$errors" -gt 0 ]]; then
        status="warn"
    fi

    emit_unified_report "checkov" "$status" "$warnings" "$errors" "$findings" "$duration"

    if [[ "$status" == "fail" ]]; then
        log_error "Checkov: ${errors} failed checks (max: ${max_e})"
        return 1
    else
        log_ok "Checkov: ${errors} failed checks — ${status}"
        return 0
    fi
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    local linter_name="${1:-}"

    # Handle --list flag
    if [[ "$linter_name" == "--list" ]]; then
        echo "Registered plugins:"
        for plugin in "${!PLUGINS[@]}"; do
            echo "  - ${plugin} → ${PLUGINS[$plugin]}()"
        done
        exit 0
    fi

    # Validate argument
    if [[ -z "$linter_name" ]]; then
        log_error "Usage: $0 <linter_name>"
        log_error "Available linters: ${!PLUGINS[*]}"
        exit 2
    fi

    # Check if plugin is registered
    if [[ -z "${PLUGINS[$linter_name]+_}" ]]; then
        log_error "Unknown linter: '${linter_name}'"
        log_error "Available linters: ${!PLUGINS[*]}"
        exit 2
    fi

    log_info "Executing plugin: ${linter_name} (strictness: ${STRICTNESS_LEVEL})"

    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR" 2>/dev/null || true

    # Run the plugin function and capture output
    local plugin_func="${PLUGINS[$linter_name]}"
    local exit_code=0
    local output

    output=$("$plugin_func") || exit_code=$?

    # Write report to file
    echo "$output" > "$REPORT_FILE"
    log_info "Report written to: ${REPORT_FILE}"

    # Also output to stdout for pipeline consumption
    echo "$output"

    # Exit with plugin's exit code
    exit "$exit_code"
}

# =============================================================================
# ENTRY POINT
# =============================================================================
main "$@"
