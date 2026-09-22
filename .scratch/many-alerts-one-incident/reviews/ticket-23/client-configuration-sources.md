# Mediated-client configuration source map

**Status:** bounded documentation research; official sources only; retrieved 2026-09-22.

This note records what the current Claude Code documentation and Node.js documentation say about mediated endpoint, credential-header, and custom-CA configuration. It does not establish behavior of the locally registered Claude Code CLI. The task context identifies that CLI as version 2.1.278; no `claude` process was launched, no installed package was executed or inspected, and no authentication, provider or model request was made. Only public documentation was retrieved.

## Documented configuration contract

| Setting | Documented behavior | Primary source |
| --- | --- | --- |
| `ANTHROPIC_BASE_URL` | Overrides the API endpoint so requests can route through a proxy or gateway. On a non-first-party host, MCP tool search is disabled by default; the docs say to set `ENABLE_TOOL_SEARCH=true` only when the proxy forwards `tool_reference` blocks. | [Claude Code environment variables](https://code.claude.com/docs/en/env-vars) (`ANTHROPIC_BASE_URL`) |
| `ANTHROPIC_AUTH_TOKEN` | The configured value is sent in the `Authorization` header with `Bearer ` prefixed. The gateway guide classifies this as the choice when the gateway expects a bearer token or Authorization header. | [Claude Code environment variables](https://code.claude.com/docs/en/env-vars) (`ANTHROPIC_AUTH_TOKEN`); [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect) (credential variable and header mapping sections) |
| `ANTHROPIC_API_KEY` | The configured API key is sent in the `X-Api-Key` header (the gateway guide writes the equivalent name as lowercase `x-api-key`). The gateway guide classifies this as the choice when the gateway expects an API key or x-api-key. | [Claude Code environment variables](https://code.claude.com/docs/en/env-vars) (`ANTHROPIC_API_KEY`); [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect) |
| `NODE_EXTRA_CA_CERTS` | Claude Code documents this as the custom-CA path for enterprise TLS. Node documents that the PEM file extends the well-known root CAs, is read when the Node process starts, and has no effect when a TLS/HTTPS client explicitly supplies a `ca` option. | [Enterprise network configuration](https://code.claude.com/docs/en/corporate-proxy) (custom CA section); [Node.js CLI: `NODE_EXTRA_CA_CERTS`](https://nodejs.org/api/cli.html#node_extra_ca_certsfile) |

The gateway guide's documented verification example posts to `$ANTHROPIC_BASE_URL/v1/messages`, with the bearer or x-api-key header selected to match the configured credential. It says a `401` means the credential was rejected and advises switching to the other variable when the variable was guessed. This is a documentation example and does not prove that a particular installed client emitted that request.

Claude Code's enterprise network page further documents a default CA policy of bundled Mozilla certificates plus the OS certificate store. It says OS-store support depends on the runtime (`tls.getCACertificates`), with the native installer always supporting it and npm installs requiring Node 22.15 or later; on older Node versions, only the bundled set and `NODE_EXTRA_CA_CERTS` apply. The same page says environment variables should be set before launch, and that `NODE_EXTRA_CA_CERTS` may also be placed in an applicable settings `env` block.

Node's own contract is narrower than “all clients trust this CA”: the extra PEM roots are loaded at process launch, malformed or missing files produce a one-time warning and otherwise are ignored, and an explicit per-client `ca` option bypasses both well-known and extra certificates. Node also documents that `NODE_EXTRA_CA_CERTS` is ignored for setuid-root or Linux-file-capability executions. These conditions should remain visible in any fixture result.

## Explicit boundaries and absences

- The official docs do not state a deterministic precedence rule when both `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` are set together. They document each mapping and precedence over a saved login, but do not authorize inferring which of the two wins. A fixture should run the two credential cases separately and leave the other variable unset.
- The docs do not establish that setting `ANTHROPIC_BASE_URL` rewrites arbitrary paths, adds or removes a trailing `/v1`, or changes every auxiliary request. The documented verification path is the specific `$ANTHROPIC_BASE_URL/v1/messages` example.
- The docs do not prove the behavior of the locally registered 2.1.278 executable. A `/status`, debug log, captured request, or successful loopback exchange would supply runtime evidence after technical admission under the existing authorization; none was performed here.
- The docs do not make a synthetic loopback exchange evidence of Anthropic authentication, provider routing, model availability, billing, or native-client qualification. They also do not promise that `NODE_EXTRA_CA_CERTS` affects a client that supplies its own TLS `ca` option.
- Claude Code explicitly says cloud sessions ignore `NODE_EXTRA_CA_CERTS` (and related TLS variables) when supplied through a settings-file `env` block because the hosting environment manages the provider connection. This source map therefore applies to a local mediated client only; it must not be promoted to cloud-session behavior.

## Bounded fixture implications

For a local loopback TLS fixture, set the endpoint and exactly one credential variable before starting the client process; capture the request path and case-insensitive header names without recording secret values. Use a CA PEM file through `NODE_EXTRA_CA_CERTS` before process launch, and retain a negative case without the CA only if the fixture can classify the resulting trust failure without making a provider call. Keep the response canned and deterministic. Report all such observations as synthetic/runtime evidence, separately from this documentation map; no model or external provider request is implied.

## Official sources

- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect)
- [Enterprise network configuration](https://code.claude.com/docs/en/corporate-proxy)
- [Node.js command-line API: `NODE_EXTRA_CA_CERTS`](https://nodejs.org/api/cli.html#node_extra_ca_certsfile)
