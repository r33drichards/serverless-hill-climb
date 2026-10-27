import {bundlePath} from './git-bundle.mjs';
export const policies={
 '/assets/hillclimb-fs-v1.rego':`package mcp.filesystem
 default allow = false
 allow if {
  startswith(input.path, "/work/")
  not contains(input.path, "..")
  not input.destination
 }
 allow if {
  startswith(input.path, "/work/")
  startswith(input.destination, "/work/")
  not contains(input.path, "..")
  not contains(input.destination, "..")
 }`,
 '/assets/hillclimb-fetch-v1.rego':`package mcp.fetch
 default allow = false
 allow if {
  input.url_parsed.scheme == "https"
  input.url_parsed.host == "serverless-hill-climb.rwendt1337.workers.dev"
  startswith(input.url_parsed.path, "/git/")
  input.method in {"GET", "POST"}
 }`,
 '/assets/hillclimb-modules-v1.rego':`package mcp.modules
 default allow = false
 allow if {
  input.specifier_type == "url"
  input.url_parsed.scheme == "https"
  input.url_parsed.host == "serverless-hill-climb.rwendt1337.workers.dev"
  input.url_parsed.path == "${bundlePath}"
 }`
};
