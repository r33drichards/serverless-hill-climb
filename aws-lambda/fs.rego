package mcp.filesystem

default allow = false

allow if {
    input.operation in {"readFile", "writeFile", "exists", "stat"}
    startswith(input.path, "/mnt/workspace/")
    not contains(input.path, "..")
    not input.destination
}
