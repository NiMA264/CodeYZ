# CodeYZ Agent Instructions

## Goal

Build CodeYZ: a local coding agent similar to Codex using OpenAI API.

## Core Principles

* Minimize token usage
* Never send full repositories
* Never send secrets (.env, keys)
* Always prefer diffs over full files
* Use summaries for large files
* Run code locally in Docker
* Ask before commit, push, deploy

## Workflow

1. Understand task
2. Create minimal plan
3. Select relevant files only
4. Apply patch (not full rewrite)
5. Run tests locally
6. Fix errors iteratively
7. Show diff
8. Ask for approval before commit

## Tools Available

* read_file
* write_file
* list_files
* search_code
* run_shell (restricted)
* run_tests
* git_diff
* git_commit

## Rules

* Never modify files outside project
* Never execute dangerous commands
* Never delete large parts of project without confirmation
* Always keep changes minimal and incremental

## Output Style

* Be concise
* Show only necessary code
* Prefer diffs

## Architecture Notes

* Workspace-based file access via current project path
* Multiple projects supported via allowlist
* All file operations must respect workspace boundary
* Context builder and tools must use same path model

## Execution

* Code execution may run locally or via Docker (preferred)
* Sandbox model should be enforced for safety

## Patching

* Prefer unified diffs over full file replacement
* Full rewrites only if explicitly required
