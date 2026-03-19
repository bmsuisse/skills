
#!/usr/bin/env bash

# Exit on error
set -e

# Color codes
RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RESET="\033[0m"

log() {
	local msg="$1"
	echo -e "${BLUE}$msg${RESET}"
}

warn() {
	local msg="$1"
	echo -e "${RED}$msg${RESET}"
}

header() {
	local msg="$1"
	echo -e "${CYAN}=============== $msg ===============${RESET}"
}

install_prettier() {
    header "installing prettier"

    if npm list prettier --depth=0 >/dev/null 2>&1; then
        log "prettier is already installed"
    else
        log "installing prettier..."
        npm install --save-dev prettier || {
            warn "failed to install prettier"
            exit 1
        }
        log "prettier installed successfully"
    fi
}

install_dependencies(){
    header "installing uv dependencies"
    uv sync --group format || warn "failed to install uv dependencies"

    install_prettier
}

check_dependencies(){
    header "checking dependencies"

    log "running deptry..."
    uv run deptry . || warn "deptry found missing dependencies"
    log "all dependencies are satisfied"
}

format_python() {
	header "python formatting started"

	log "running autoflake..."
	uv run autoflake -r -i . || warn "autoflake failed"

	log "running isort..."
	uv run isort . || warn "isort failed"

	log "running pycln..."
	uv run pycln . || warn "pycln failed (optional)"

	log "running ruff format..."
	uv run ruff format . || warn "ruff format failed"

	log "running ruff check..."
	uv run ruff check . --fix || warn "ruff check failed"

	log "running pyright..."
	uv run pyright . || warn "pyright found issues"

	log "Python formatting completed"
}

format_sql() {
    header "sql formatting started"

    log "running sqlfmt..."
    uv run sqlfmt .

    log "SQL formatting completed"
}

format_yaml() {
    header "yaml formatting started"

    log "running yamlfix..."
    uv run yamlfix . --exclude .venv --exclude .dev --exclude .idea --include *.yml

    log "YAML formatting completed"
}

format_prettier() {
    header "prettier formatting started"

    npx prettier --write "{,*/**/}*.{ts,tsx,js,jsx,css,scss,json,md}" || {
        warn "prettier failed"
        exit 1
    }
    log "prettier formatting completed"
}

format_all() {
    format_python
    format_sql
    format_yaml
    format_prettier
}

format_commit(){
    format_all

    header "committing formatted code..."

    git add .
    git commit -m "chore: format code"

    log "formatted code committed"
}

show_help() {
		echo -e "   ${MAGENTA}Usage: $0 <command>${RESET}"
		echo -e "   ${CYAN}Available commands:${RESET}"
		echo -e "       - ${GREEN}format-python${RESET}            : Run Python code formatters and linters"
        echo -e "       - ${GREEN}format-sql${RESET}               : Run SQL formatter"
        echo -e "       - ${GREEN}format-yaml${RESET}              : Run YAML formatter"
        echo -e "       - ${GREEN}format-all${RESET}               : Run all formatters"
        echo -e "       - ${GREEN}format-prettier${RESET}          : Run prettier for all non-Python files"
        echo -e "       - ${GREEN}format-commit${RESET}            : Format code and commit changes"
        echo -e "       - ${GREEN}install-dependencies${RESET}     : Install dev and test dependencies"
		echo -e "       - ${GREEN}check-dependencies${RESET}       : Check for missing dependencies"
		echo -e "       - ${GREEN}help${RESET}                     : Show help"
}

main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 1
    fi

    local command="$1"
    shift

    case "$command" in
        format-python)
            format_python "$@"
            ;;
        format-sql)
            format_sql "$@"
            ;;
        format-prettier)
            format_prettier "$@"
            ;;
        format-yaml)
            format_yaml "$@"
            ;;
        format)
            format_all "$@"
            ;;
        format-all)
            format_all "$@"
            ;;
        format-commit)
            format_commit "$@"
            ;;
        install-dependencies)
            install_dependencies "$@"
            ;;
        check-dependencies)
            check_dependencies "$@"
            ;;
        help|*)
            show_help
            ;;
    esac
}

main "$@"