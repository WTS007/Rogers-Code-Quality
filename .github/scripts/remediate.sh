#!/usr/bin/env bash
# =============================================================================
# Project Nexus — AI Remediation Script (normalized LF)
# =============================================================================
# Parses build error logs and generates contextual fixes.
# Accepts error log via stdin or file path argument.
#
# Usage:
#   ./remediate.sh <error_log_file>
#   cat error_log.txt | ./remediate.sh
#
# Output: JSON report to stdout
#   { "strategy": "...", "files_modified": [...], "confidence": 0.85 }
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# BYOM INTEGRATION POINT
# Replace this function with a custom LLM API call to generate patches.
# Input:  $1 = error context (string)
# Output: patch suggestion (string) to stdout
# =============================================================================
call_external_model() {
    local error_context="${1:-}"
    # -------------------------------------------------------------------------
    # EXAMPLE: Uncomment and configure for your LLM endpoint
    # -------------------------------------------------------------------------
    # curl -s -X POST "${NEXUS_MODEL_ENDPOINT:-http://localhost:8080/v1/completions}" \
    #   -H "Authorization: Bearer ${NEXUS_MODEL_API_KEY:-}" \
    #   -H "Content-Type: application/json" \
    #   -d "{
    #     \"model\": \"${NEXUS_MODEL_NAME:-gpt-4}\",
    #     \"temperature\": ${NEXUS_MODEL_TEMPERATURE:-0.2},
    #     \"messages\": [
    #       {\"role\": \"system\", \"content\": \"You are a code remediation assistant. Generate minimal, correct patches.\"},
    #       {\"role\": \"user\", \"content\": \"Fix this build error:\\n${error_context}\"}
    #     ]
    #   }" | jq -r '.choices[0].message.content // empty'
    # -------------------------------------------------------------------------
    echo ""
}

# =============================================================================
# GLOBALS
# =============================================================================
declare -a FILES_MODIFIED=()
STRATEGY="none"
CONFIDENCE=0.0
WORK_DIR="$(pwd)"
REMEDIATION_LOG="/tmp/nexus_remediation_$$.log"

# =============================================================================
# LOGGING
# =============================================================================
log_info()  { echo "[nexus:remediate] ℹ️  $*" >&2; }
log_warn()  { echo "[nexus:remediate] ⚠️  $*" >&2; }
log_error() { echo "[nexus:remediate] ❌ $*" >&2; }
log_ok()    { echo "[nexus:remediate] ✅ $*" >&2; }

# =============================================================================
# READ ERROR LOG
# =============================================================================
read_error_log() {
    local error_content=""

    if [[ $# -ge 1 ]] && [[ -f "$1" ]]; then
        error_content=$(cat "$1")
    elif [[ ! -t 0 ]]; then
        error_content=$(cat -)
    else
        log_error "No error log provided. Pass a file path or pipe via stdin."
        emit_report
        exit 0
    fi

    if [[ -z "$error_content" ]]; then
        log_warn "Error log is empty — nothing to remediate."
        STRATEGY="no_errors"
        CONFIDENCE=1.0
        emit_report
        exit 0
    fi

    echo "$error_content"
}

# =============================================================================
# PATTERN CLASSIFIERS
# =============================================================================
classify_missing_file() {
    local log="$1"
    # Matches: FileNotFoundError, ENOENT, No such file or directory, cannot open
    echo "$log" | grep -iE \
        '(no such file|filenotfounderror|enoent|cannot open|file not found|missing file|ModuleNotFoundError.*No module)' \
        || true
}

classify_syntax_error() {
    local log="$1"
    echo "$log" | grep -iE \
        '(syntax ?error|unexpected token|parsing error|indentation|unterminated|SyntaxError)' \
        || true
}

classify_dependency_missing() {
    local log="$1"
    echo "$log" | grep -iE \
        '(cannot find module|no matching distribution|could not resolve|ModuleNotFoundError|ImportError|ERR! missing|peer dep|ERESOLVE|not found in registry)' \
        || true
}

classify_test_failure() {
    local log="$1"
    echo "$log" | grep -iE \
        '(FAIL|test.*failed|assertion.*error|expect.*to|AssertionError|pytest.*FAILED|✗|✘|FAILURES)' \
        || true
}

# =============================================================================
# REMEDIATION HANDLERS
# =============================================================================
handle_missing_file() {
    local matches="$1"
    log_info "Detected MISSING FILE errors"

    while IFS= read -r line; do
        # Extract file path from error message
        local filepath=""

        # Python: FileNotFoundError: [Errno 2] No such file or directory: 'path'
        filepath=$(echo "$line" | grep -oP "(?<=['\"])[^'\"]+(?=['\"])" | head -1)

        # Node: Error: ENOENT: no such file or directory, open 'path'
        if [[ -z "$filepath" ]]; then
            filepath=$(echo "$line" | grep -oP '(?<=open\s)[^\s]+' | tr -d "'\"" | head -1)
        fi

        # Generic: No such file or directory followed by path
        if [[ -z "$filepath" ]]; then
            filepath=$(echo "$line" | grep -oP '(?<=directory:?\s)[^\s]+' | tr -d "'\":" | head -1)
        fi

        if [[ -n "$filepath" ]] && [[ "$filepath" != "/" ]]; then
            # Determine file type and create with sensible defaults
            local dirname
            dirname=$(dirname "$filepath")

            if [[ "$dirname" != "." ]] && [[ ! -d "$dirname" ]]; then
                mkdir -p "$dirname" 2>/dev/null || true
            fi

            local extension="${filepath##*.}"
            case "$extension" in
                py)
                    cat > "$filepath" <<'PYEOF'
# Auto-generated by Nexus AI Remediation
# TODO: Implement required functionality

def main():
    pass

if __name__ == "__main__":
    main()
PYEOF
                    ;;
                js|ts)
                    cat > "$filepath" <<'JSEOF'
// Auto-generated by Nexus AI Remediation
// TODO: Implement required functionality

module.exports = {};
JSEOF
                    ;;
                json)
                    echo '{}' > "$filepath"
                    ;;
                yml|yaml)
                    echo '# Auto-generated by Nexus AI Remediation' > "$filepath"
                    ;;
                txt|md)
                    echo '# Auto-generated by Nexus AI Remediation' > "$filepath"
                    ;;
                cfg|ini|conf|config)
                    echo '# Auto-generated by Nexus AI Remediation' > "$filepath"
                    ;;
                *)
                    touch "$filepath"
                    ;;
            esac

            FILES_MODIFIED+=("$filepath")
            log_ok "Created missing file: $filepath"
        fi
    done <<< "$matches"

    STRATEGY="missing_file_creation"
    CONFIDENCE=0.85
}

handle_dependency_missing() {
    local matches="$1"
    log_info "Detected DEPENDENCY errors"

    local npm_deps=()
    local pip_deps=()

    while IFS= read -r line; do
        # npm: Cannot find module 'foo'
        local npm_mod
        npm_mod=$(echo "$line" | grep -oP "(?<=Cannot find module ')[^']+" || true)
        if [[ -n "$npm_mod" ]]; then
            npm_deps+=("$npm_mod")
            continue
        fi

        # npm: ERR! missing / not found in registry
        npm_mod=$(echo "$line" | grep -oP '(?<=ERR! missing:?\s)\S+' | head -1 || true)
        if [[ -n "$npm_mod" ]]; then
            npm_deps+=("$npm_mod")
            continue
        fi

        # Python: ModuleNotFoundError: No module named 'foo'
        local py_mod
        py_mod=$(echo "$line" | grep -oP "(?<=No module named ')[^']+" || true)
        if [[ -n "$py_mod" ]]; then
            pip_deps+=("$py_mod")
            continue
        fi

        # Python: ImportError: cannot import name 'x' from 'y'
        py_mod=$(echo "$line" | grep -oP "(?<=from ')[^']+" || true)
        if [[ -n "$py_mod" ]]; then
            pip_deps+=("$py_mod")
            continue
        fi

        # pip: No matching distribution found for foo
        py_mod=$(echo "$line" | grep -oP '(?<=distribution found for )\S+' || true)
        if [[ -n "$py_mod" ]]; then
            pip_deps+=("$py_mod")
            continue
        fi
    done <<< "$matches"

    # Generate install commands
    if [[ ${#npm_deps[@]} -gt 0 ]]; then
        local unique_npm
        unique_npm=$(printf '%s\n' "${npm_deps[@]}" | sort -u | tr '\n' ' ')
        log_ok "Suggested fix: npm install ${unique_npm}"

        # If package.json exists, try to add deps
        if [[ -f "${WORK_DIR}/package.json" ]]; then
            echo "npm install --save ${unique_npm}" >> "${WORK_DIR}/.nexus-install-commands.sh"
            FILES_MODIFIED+=(".nexus-install-commands.sh")
        fi
    fi

    if [[ ${#pip_deps[@]} -gt 0 ]]; then
        local unique_pip
        unique_pip=$(printf '%s\n' "${pip_deps[@]}" | sort -u | tr '\n' ' ')
        log_ok "Suggested fix: pip install ${unique_pip}"

        # Append to requirements.txt if it exists or create one
        for dep in $(printf '%s\n' "${pip_deps[@]}" | sort -u); do
            if [[ -f "${WORK_DIR}/requirements.txt" ]]; then
                if ! grep -qF "$dep" "${WORK_DIR}/requirements.txt"; then
                    echo "$dep" >> "${WORK_DIR}/requirements.txt"
                fi
            else
                echo "$dep" >> "${WORK_DIR}/requirements.txt"
            fi
        done
        FILES_MODIFIED+=("requirements.txt")
    fi

    STRATEGY="dependency_resolution"
    CONFIDENCE=0.75
}

handle_syntax_error() {
    local matches="$1"
    log_info "Detected SYNTAX errors — logging for AI model intervention"

    local syntax_report="${WORK_DIR}/.nexus-syntax-errors.log"
    echo "# Nexus AI — Syntax Errors Detected" > "$syntax_report"
    echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$syntax_report"
    echo "" >> "$syntax_report"

    while IFS= read -r line; do
        # Extract file:line patterns
        local file_ref
        file_ref=$(echo "$line" | grep -oP '[^\s:]+\.(py|js|ts|jsx|tsx):\d+' | head -1 || true)

        if [[ -n "$file_ref" ]]; then
            local err_file="${file_ref%%:*}"
            local err_line="${file_ref##*:}"
            echo "FILE: ${err_file}  LINE: ${err_line}" >> "$syntax_report"
            echo "  ERROR: ${line}" >> "$syntax_report"
            echo "" >> "$syntax_report"
            log_warn "Syntax error in ${err_file}:${err_line}"
        else
            echo "UNRESOLVED: ${line}" >> "$syntax_report"
            echo "" >> "$syntax_report"
        fi
    done <<< "$matches"

    # Attempt BYOM integration for patch generation
    local model_response
    model_response=$(call_external_model "$matches")
    if [[ -n "$model_response" ]]; then
        echo "" >> "$syntax_report"
        echo "# --- BYOM Model Suggestion ---" >> "$syntax_report"
        echo "$model_response" >> "$syntax_report"
        CONFIDENCE=0.70
    else
        CONFIDENCE=0.40
    fi

    FILES_MODIFIED+=(".nexus-syntax-errors.log")
    STRATEGY="syntax_error_triage"
}

handle_test_failure() {
    local matches="$1"
    log_info "Detected TEST FAILURES — logging for review"

    local test_report="${WORK_DIR}/.nexus-test-failures.log"
    echo "# Nexus AI — Test Failure Report" > "$test_report"
    echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$test_report"
    echo "" >> "$test_report"
    echo "$matches" >> "$test_report"

    FILES_MODIFIED+=(".nexus-test-failures.log")
    STRATEGY="test_failure_triage"
    CONFIDENCE=0.30
}

# =============================================================================
# REPORT EMITTER
# =============================================================================
emit_report() {
    local files_json="[]"
    if [[ ${#FILES_MODIFIED[@]} -gt 0 ]]; then
        files_json=$(printf '%s\n' "${FILES_MODIFIED[@]}" | jq -R . | jq -s .)
    fi

    cat <<JSONEOF
{
  "strategy": "${STRATEGY}",
  "files_modified": ${files_json},
  "confidence": ${CONFIDENCE},
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pipeline": "nexus-ai-remediation",
  "strictness": "${STRICTNESS_LEVEL:-medium}"
}
JSONEOF
}

# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================
main() {
    log_info "Nexus AI Remediation Engine — Starting"
    log_info "Working directory: ${WORK_DIR}"

    # Read error log content
    local error_log
    error_log=$(read_error_log "$@")

    # Save raw log for debugging
    echo "$error_log" > "$REMEDIATION_LOG"

    # Classify errors by type (priority order)
    local missing_files syntax_errors dep_errors test_failures
    missing_files=$(classify_missing_file "$error_log")
    syntax_errors=$(classify_syntax_error "$error_log")
    dep_errors=$(classify_dependency_missing "$error_log")
    test_failures=$(classify_test_failure "$error_log")

    # Count matches to determine primary strategy
    local mf_count se_count de_count tf_count
    mf_count=$(echo "$missing_files" | grep -c . 2>/dev/null || true)
    mf_count=$(echo "$mf_count" | tr -d '\r')
    se_count=$(echo "$syntax_errors" | grep -c . 2>/dev/null || true)
    se_count=$(echo "$se_count" | tr -d '\r')
    de_count=$(echo "$dep_errors" | grep -c . 2>/dev/null || true)
    de_count=$(echo "$de_count" | tr -d '\r')
    tf_count=$(echo "$test_failures" | grep -c . 2>/dev/null || true)
    tf_count=$(echo "$tf_count" | tr -d '\r')

    log_info "Classification: missing_files=$mf_count syntax=$se_count deps=$de_count tests=$tf_count"

    # Process each error type (multiple can fire; last one sets strategy)
    local strategies_applied=0

    if [[ "$mf_count" -gt 0 ]] && [[ -n "$missing_files" ]]; then
        handle_missing_file "$missing_files"
        ((strategies_applied++)) || true
    fi

    if [[ "$de_count" -gt 0 ]] && [[ -n "$dep_errors" ]]; then
        handle_dependency_missing "$dep_errors"
        ((strategies_applied++)) || true
    fi

    if [[ "$se_count" -gt 0 ]] && [[ -n "$syntax_errors" ]]; then
        handle_syntax_error "$syntax_errors"
        ((strategies_applied++)) || true
    fi

    if [[ "$tf_count" -gt 0 ]] && [[ -n "$test_failures" ]]; then
        handle_test_failure "$test_failures"
        ((strategies_applied++)) || true
    fi

    # Multi-strategy: combine
    if [[ "$strategies_applied" -gt 1 ]]; then
        STRATEGY="multi_strategy"
        # Average down confidence for multi-error scenarios
        CONFIDENCE=$(echo "scale=2; $CONFIDENCE * 0.8" | bc 2>/dev/null || echo "$CONFIDENCE")
    fi

    if [[ "$strategies_applied" -eq 0 ]]; then
        STRATEGY="unrecognized_error"
        CONFIDENCE=0.10
        log_warn "Could not classify errors — manual review required"

        # Attempt BYOM as fallback
        local model_response
        model_response=$(call_external_model "$error_log")
        if [[ -n "$model_response" ]]; then
            echo "$model_response" > "${WORK_DIR}/.nexus-model-suggestion.txt"
            FILES_MODIFIED+=(".nexus-model-suggestion.txt")
            STRATEGY="byom_fallback"
            CONFIDENCE=0.50
        fi
    fi

    log_info "Strategy: ${STRATEGY} | Confidence: ${CONFIDENCE} | Files: ${#FILES_MODIFIED[@]}"

    # Emit JSON report to stdout
    emit_report

    # Cleanup
    rm -f "$REMEDIATION_LOG" 2>/dev/null || true

    log_ok "Remediation complete"
}

# =============================================================================
# ENTRY POINT
# =============================================================================
main "$@"
