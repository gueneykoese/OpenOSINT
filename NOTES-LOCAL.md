# OpenOSINT — local install notes (Akberg)

Installed 2026-08-23. Repo: https://github.com/OpenOSINT/OpenOSINT (v2.25.0, MIT).

## Layout
- `.venv/`         — isolated Python 3.12 env. Nothing installed to system Python.
- `run-mcp.sh`     — MCP launcher. Prepends `.venv/bin` to PATH so the
                     subprocess-backed tools (holehe/sherlock/sublist3r) resolve,
                     then execs `python -m openosint.mcp_server`.
- `.env`           — API keys (mode 0600, all currently unset/commented).
- `constraints.txt`— see the pin below.

## Registered with Claude Code
    claude mcp add --scope user openosint /Users/guneykose/Desktop/Merhaba/openosint/run-mcp.sh

User scope, so it loads in every project. Remove with `claude mcp remove openosint`.

## IMPORTANT: the mcp pin
pyproject declares `mcp>=1.0.0`. Installing fresh pulls MCP SDK **2.0.0**, which
removed the low-level `@app.list_tools()` decorator that `mcp_server.py` uses —
the server crashes on import. Pinned to `mcp==1.29.0`.

If you ever re-run `pip install -e .`, re-apply the pin:

    ./.venv/bin/pip install -e . -c constraints.txt

## Working with no API keys
whois, dns, ip, generate_dorks, search_footprint, search_github (60 req/h unauth),
search_domain (sublist3r), search_username (sherlock), search_email (holehe).

Needs a key (each returns a clear "not set" message otherwise): shodan,
virustotal, censys, abuseipdb, ip2location, breach (HIBP), dorks_live +
scrape_url (Bright Data).

## Fixed: two false-finding bugs in search_dns
Both surfaced during a live supplier check and both would have put wrong
conclusions into a due-diligence report.

1. **DMARC policy inverted.** `_analyze_dmarc` substring-matched `"p=none" in
   record`. A record reading `p=reject; sp=none` contains the substring
   `p=none`, so the strongest policy tier was reported as the weakest. Now
   parsed by tag; `sp=` is reported separately as its own (real) finding.
2. **Failed lookup reported as absence.** A TXT timeout was swallowed by
   `except Exception: return []`, and `_analyze_spf` then emitted "No SPF record
   found — anyone can spoof email from this domain" for a domain with a strict
   `-all` SPF. `_query` now retries over TCP (large TXT sets exceed what some
   local resolvers return over UDP) and registers genuine failures, which are
   reported as `[?] undetermined` and listed in a trailing FAILED line. Same
   treatment applied to DKIM probes.

Note the shape: this is the identical flaw the original sublist3r problem had —
silence rendered as a finding. Worth checking for elsewhere in the codebase.

`_query`'s happy path deliberately keeps its original `resolver.resolve(domain,
rdtype)` signature; the `tcp=True` kwarg only appears on retry, so the resolver
doubles in tests/test_dns.py still work.

## Known limitation
`search_whois` fails on `.wine` — IANA publishes no WHOIS referral server for that
TLD (Binky Moon / Identity Digital is RDAP-only), so `python-whois` gets nothing
back. Not an install fault; verified working on .com. Use an RDAP lookup for
RDAP-only TLDs.

## Not installed
`phoneinfoga` (Go binary, no Homebrew on this machine). `search_phone` will report
it as missing. Phone-number enumeration is the least useful and most GDPR-exposed
tool for B2B counterparty checks anyway.

## Patched: search_domain now uses Certificate Transparency
`sublist3r` installs and runs but returns **zero** results even on control
domains — DNSdumpster's scraper throws `IndexError` on CSRF parsing (site
redesigned), VirusTotal blocks it, Netcraft returns nothing. Upstream is
unmaintained since 2019.

`openosint/tools/search_domain.py` was rewritten to query Certificate
Transparency logs instead, with sublist3r demoted to a secondary source:

  * **crt.sh** — primary. Free, no key. Retries 3x with backoff on 502/404,
    both of which crt.sh emits transiently (a genuine empty result is a 200
    with `[]`, never a 404).
  * **certspotter** — fallback when crt.sh is down. Unauthenticated and rate
    limited, and returns only unexpired issuances, so it reports fewer hosts
    than crt.sh (3 vs 10 on akberg.wine). Better than nothing.
  * **sublist3r** — still run, concurrently, merged in if it ever works again.

The footer always reports per-source counts, so a silent backend failure can
never be mistaken for "this domain has no subdomains" — which is exactly how
the original failed.

Scope filtering matters here: one crt.sh entry's `name_value` holds *every* SAN
on that certificate, including unrelated domains sharing it. A naive filter
leaks hosts like `akberg.wine.internationalfestival.pl`. Each SAN is
suffix-checked individually. Wildcards keep their `*.` prefix rather than being
stripped to the apex.

Signature is unchanged, so all six callers (mcp_server, agent, web_server,
cloud, playbooks/runner, tests) are unaffected. Full suite: **510 passed**.

## Fixed: aiohttp TLS failure on this host
aiohttp's default SSL context on this machine rejected **every** HTTPS host
(api.github.com, crt.sh, api.certspotter.com, api.abuseipdb.com) with
`CERTIFICATE_VERIFY_FAILED`. Not a MITM proxy and not a certifi gap — these
servers transmit their own root in the chain, and OpenSSL then demands a path to
a self-signed root rather than anchoring on the trusted intermediate it already
has. curl, httpx and every `requests`-based tool were unaffected; only the
aiohttp callers broke.

Fix: `get_ssl_context()` in `openosint/utils.py` (certifi +
`VERIFY_X509_PARTIAL_CHAIN`), passed as `ssl=` at all three aiohttp request
sites — the only ones in the codebase:

  * `openosint/tools/search_domain.py`     (_get_json)
  * `openosint/tools/search_github.py`     (_get)
  * `openosint/tools/search_abuseipdb.py`  (_fetch_abuseipdb_data)

Verified A/B on api.abuseipdb.com: default context fails with
`ClientConnectorCertificateError`; patched context completes the handshake and
gets a real API response. `search_github` confirmed returning live data.

## Fixed: two false-finding bugs in search_dns
Both surfaced during a live supplier check and both would have put wrong
conclusions into a due-diligence report.

1. **DMARC policy inverted.** `_analyze_dmarc` substring-matched `"p=none" in
   record`. A record reading `p=reject; sp=none` contains the substring
   `p=none`, so the strongest policy tier was reported as the weakest. Now
   parsed by tag; `sp=` is reported separately as its own (real) finding.
2. **Failed lookup reported as absence.** A TXT timeout was swallowed by
   `except Exception: return []`, and `_analyze_spf` then emitted "No SPF record
   found — anyone can spoof email from this domain" for a domain with a strict
   `-all` SPF. `_query` now retries over TCP (large TXT sets exceed what some
   local resolvers return over UDP) and registers genuine failures, which are
   reported as `[?] undetermined` and listed in a trailing FAILED line. Same
   treatment applied to DKIM probes.

Note the shape: this is the identical flaw the original sublist3r problem had —
silence rendered as a finding. Worth checking for elsewhere in the codebase.

`_query`'s happy path deliberately keeps its original `resolver.resolve(domain,
rdtype)` signature; the `tcp=True` kwarg only appears on retry, so the resolver
doubles in tests/test_dns.py still work.

## Known limitation
`search_whois` fails on `.wine` — IANA publishes no WHOIS referral server for that
TLD (Binky Moon / Identity Digital is RDAP-only), so `python-whois` gets nothing
back. Not an install fault; verified working on .com. Use an RDAP lookup for
RDAP-only TLDs.

## Not installed
`phoneinfoga` (Go binary, no Homebrew on this machine). `search_phone` will report
it as missing. Phone-number enumeration is the least useful and most GDPR-exposed
tool for B2B counterparty checks anyway.

## Patched: search_domain now uses Certificate Transparency
`sublist3r` installs and runs but returns **zero** results even on control
domains — DNSdumpster's scraper throws `IndexError` on CSRF parsing (site
redesigned), VirusTotal blocks it, Netcraft returns nothing. Upstream is
unmaintained since 2019.

`openosint/tools/search_domain.py` was rewritten to query Certificate
Transparency logs instead, with sublist3r demoted to a secondary source:

  * **crt.sh** — primary. Free, no key. Retries 3x with backoff on 502/404,
    both of which crt.sh emits transiently (a genuine empty result is a 200
    with `[]`, never a 404).
  * **certspotter** — fallback when crt.sh is down. Unauthenticated and rate
    limited, and returns only unexpired issuances, so it reports fewer hosts
    than crt.sh (3 vs 10 on akberg.wine). Better than nothing.
  * **sublist3r** — still run, concurrently, merged in if it ever works again.

The footer always reports per-source counts, so a silent backend failure can
never be mistaken for "this domain has no subdomains" — which is exactly how
the original failed.

Scope filtering matters here: one crt.sh entry's `name_value` holds *every* SAN
on that certificate, including unrelated domains sharing it. A naive filter
leaks hosts like `akberg.wine.internationalfestival.pl`. Each SAN is
suffix-checked individually. Wildcards keep their `*.` prefix rather than being
stripped to the apex.

Signature is unchanged, so all six callers (mcp_server, agent, web_server,
cloud, playbooks/runner, tests) are unaffected. Full suite: **510 passed**.

## Systemic: aiohttp TLS failure on this host — NOT yet fixed everywhere
aiohttp's default SSL context on this machine rejects **every** HTTPS host
(api.github.com, crt.sh, api.certspotter.com) with `CERTIFICATE_VERIFY_FAILED`.
Not a MITM proxy and not a certifi gap — these servers transmit their own root
in the chain, and OpenSSL then demands a path to a self-signed root rather than
anchoring on the trusted intermediate it already has. curl, httpx and the
`requests`-based tools are unaffected; only aiohttp callers break.

Fix added as `get_ssl_context()` in `openosint/utils.py` (certifi +
`VERIFY_X509_PARTIAL_CHAIN`). Verified against github, crt.sh and certspotter.

**Applied so far only to `search_domain`.** Still broken, both confirmed failing
end-to-end:
  * `search_github`   (openosint/tools/search_github.py)
  * `search_abuseipdb`(openosint/tools/search_abuseipdb.py)

Each needs `ssl=get_ssl_context()` added to its `session.get(...)` call.

## Fixed: two false-finding bugs in search_dns
Both surfaced during a live supplier check and both would have put wrong
conclusions into a due-diligence report.

1. **DMARC policy inverted.** `_analyze_dmarc` substring-matched `"p=none" in
   record`. A record reading `p=reject; sp=none` contains the substring
   `p=none`, so the strongest policy tier was reported as the weakest. Now
   parsed by tag; `sp=` is reported separately as its own (real) finding.
2. **Failed lookup reported as absence.** A TXT timeout was swallowed by
   `except Exception: return []`, and `_analyze_spf` then emitted "No SPF record
   found — anyone can spoof email from this domain" for a domain with a strict
   `-all` SPF. `_query` now retries over TCP (large TXT sets exceed what some
   local resolvers return over UDP) and registers genuine failures, which are
   reported as `[?] undetermined` and listed in a trailing FAILED line. Same
   treatment applied to DKIM probes.

Note the shape: this is the identical flaw the original sublist3r problem had —
silence rendered as a finding. Worth checking for elsewhere in the codebase.

`_query`'s happy path deliberately keeps its original `resolver.resolve(domain,
rdtype)` signature; the `tcp=True` kwarg only appears on retry, so the resolver
doubles in tests/test_dns.py still work.

## Known limitation
`search_whois` fails on `.wine` — IANA publishes no WHOIS referral server for
that TLD (Binky Moon / Identity Digital is RDAP-only), so `python-whois` gets
nothing back. Not an install fault; verified working on .com.

## Pre-existing test failure (not ours)
`tests/test_playbooks.py::test_executive_summary_counts_correct` fails when
`.venv/bin` is absent from PATH — the playbook runner gates the search_domain
step on `sublist3r` being resolvable. Fails identically on unpatched upstream.
`run-mcp.sh` always sets PATH, so this never bites at runtime. Run tests with:

    PATH="$PWD/.venv/bin:$PATH" ./.venv/bin/python -m pytest tests/ -q

## Not installed
`phoneinfoga` (Go binary, no Homebrew on this machine). `search_phone` reports
it missing. Phone enumeration is the least useful and most GDPR-exposed tool for
B2B counterparty checks anyway.
