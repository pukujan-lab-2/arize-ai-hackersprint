# Issues and pull requests from Pukujan-lab/arize-ai-hackersprint

GitHub flagged the Pukujan-lab org on 2026-11-01 and would not transfer its repositories, so this one was copied to pukujan-lab-2 with its full git history. Its issues and pull requests could not move with it; every one is kept here as a file named by its old number, so `#123` in an old commit is `00123.md`. Open issues were also recreated as new issues that name their old number (Pukujan-lab/server-management#96).

| # | Type | State | Title |
| --- | --- | --- | --- |
| [175](00175.md) | PR | open | Dictation, hands-free voice mode and a local voice (off until SPEECH_URL is set) |
| [174](00174.md) | PR | open | Catalogue 154 sources, each one checked rather than recalled |
| [173](00173.md) | PR | open | Survey the data sources past Colorado and the 137 existing components |
| [172](00172.md) | PR | open | State that this is a production legal search engine |
| [171](00171.md) | PR | open | Test whether fixing the graph merge would help (it would not) |
| [170](00170.md) | PR | merged | Measure GLiNER as a ranker, eyecite extraction, and an 80-question regression |
| [169](00169.md) | PR | merged | Compare MiniCheck, JEV and GLiNER as claim-support judges |
| [168](00168.md) | PR | open | Record how each scorer is reached |
| [167](00167.md) | PR | merged | Touch sizes follow the screen, not the width; landscape phones get a side panel |
| [166](00166.md) | PR | merged | Stop checking quotations against themselves, and record what the measurements show |
| [165](00165.md) | PR | merged | Phone: 44px touch targets and opinions open tall in the sheet |
| [164](00164.md) | Issue | open | [ISSUE]: Citation extraction accuracy of the guard is unmeasured (regex vs eyecite vs GLiNER zero-shot) |
| [163](00163.md) | Issue | open | [ISSUE]: Claim-support accuracy of the citation check is unmeasured (MiniCheck vs GLiNER2.5-Decide vs JEV) |
| [162](00162.md) | PR | merged | Let the legal engine sleep when nobody is using Precedent |
| [161](00161.md) | Issue | closed | Precedent wakes the sleeping legal engine on every health check |
| [160](00160.md) | PR | merged | Safeguard: a citation after the full stop counts for its sentence |
| [159](00159.md) | PR | merged | Pin the engine request and artifact contract capture depends on |
| [158](00158.md) | PR | merged | Tracing: report delivery to Phoenix correctly on OpenTelemetry 1.45 |
| [157](00157.md) | PR | merged | Record what an issue log is about separately from where it is filed |
| [156](00156.md) | PR | merged | Fail a topicless ACS issue log with a usage error |
| [155](00155.md) | PR | merged | Add a retrieval eval harness with blinded pooling and withheld metrics |
| [154](00154.md) | PR | merged | Tracing: send spans to Octo's Phoenix, not Arize |
| [153](00153.md) | PR | merged | Fix: the map draws nothing in production (maplibre worker was not emitted) |
| [152](00152.md) | PR | merged | Map, theme, export and chat redesign (includes #148, #149, #150) |
| [151](00151.md) | Issue | open | [ISSUE]: red-team: The built app's theme stylesheet is missing |
| [150](00150.md) | PR | closed | Export: PDF, print, share and email for a memo |
| [149](00149.md) | PR | closed | UI: light/dark/system theme, type scale, memo formatting and padding |
| [148](00148.md) | PR | closed | Map: dark vector basemap, clustering, tilt and a US-to-court tour flight |
| [147](00147.md) | PR | open | Move agent-stack pins to the certified train (ACS 0.2.0, OIO 0.3.0, CGM 0.5.13) |
| [146](00146.md) | PR | merged | deploy: run on the always-on server (systemd), not the Pro |
| [145](00145.md) | PR | closed | fix(ci): build web/ outside the root pnpm workspace |
| [144](00144.md) | PR | merged | chore: point references at Pukujan-lab after the org move |
| [143](00143.md) | PR | merged | Source pane: open a cited opinion beside the memo, with quote checks |
| [142](00142.md) | PR | merged | Fix web lockfile (add maplibre-gl) so deploy builds; drop ABA-only frontend rule |
| [141](00141.md) | Issue | open | Deploy frozen since 2026-10-20: the browser-TTS fix is merged but never shipped |
| [140](00140.md) | PR | open | Bump actions/setup-node from 4 to 7 |
| [139](00139.md) | Issue | open | [ISSUE]: red-team: SurrealDB down with silent networkx fallback (no user banner) |
| [138](00138.md) | PR | open | Map: MapLibre via react-map-gl on OpenFreeMap, correct pin placement, narration-synced flyTo tour |
| [137](00137.md) | PR | open | Gate the empty tour and the broken voice: no phantom stop, no abandoned or forgotten clip |
| [136](00136.md) | PR | merged | v3 cutover: retrieval through the engine, honest observability, the Arize snapshot back on the page |
| [135](00135.md) | Issue | open | Follow-ups: generate them, make them clickable, and surface the next-question actions |
| [134](00134.md) | Issue | open | Retrieval: meaning, relevance, and the authorities Octo already holds |
| [133](00133.md) | Issue | open | Map: show the pipeline while a run works, and name the path it actually takes |
| [132](00132.md) | Issue | open | Voice and tour: a named speaker, visible audio states, and the v1 walk |
| [131](00131.md) | Issue | open | Map: county borders, court names and dates, real placement, links and motion |
| [130](00130.md) | Issue | open | Restore the v1 working-page capabilities (O73-O79) |
| [129](00129.md) | Issue | open | v3: reading and map regressions — memo, sources, drawer, 3D map, jurisdiction zoom, map key, narration (O65–O72) |
| [128](00128.md) | Issue | closed | v3: the observability dashboard and the visual deck (O58-O64) |
| [127](00127.md) | Issue | closed | v3: composer at the bottom, and the map pans and zooms (O53-O57) |
| [126](00126.md) | Issue | open | [ISSUE]: red-team: Graph-unavailable path should keep a clear user message |
| [125](00125.md) | PR | merged | Frontend v3: four pages, the rewritten map, and the old frontend fully retired |
| [124](00124.md) | PR | merged | Point each v3 build phase at its issue |
| [123](00123.md) | Issue | closed | v3: cutover — serve the build, forward old addresses, delete static/ (O4, O5, O52) |
| [122](00122.md) | Issue | open | v3: slides — deck at /slides with keyboard control and position (O44-O46) |
| [121](00121.md) | Issue | open | v3: observability — saved runs, steps, timings, raw details (O39-O43) |
| [120](00120.md) | Issue | closed | v3: Home — composer, memo, sources, follow-ups, run info, one Listen (O7-O16, O36) |
| [119](00119.md) | Issue | closed | v3: skeleton, map and tour (O1-O6, O17-O38, O47-O52) |
| [118](00118.md) | PR | merged | Write the acceptance tests the v3 rebuild must satisfy |
| [117](00117.md) | PR | merged | Approve the frontend v3 spec and withdraw the builder stack rule |
| [116](00116.md) | PR | merged | V2 composer: Ask becomes Follow-up, New question reset, pill slider, sent-question strip (#103) |
| [115](00115.md) | PR | merged | Retire the legacy /map: /map serves the v2 map experience (#102) |
| [114](00114.md) | PR | merged | V2: icon rail is the only navigation (#101) |
| [113](00113.md) | PR | merged | V2: Listen button and vertical tour controls (#105) |
| [112](00112.md) | PR | merged | Stop Dependabot pip version PRs (uv universal lock) |
| [111](00111.md) | PR | closed | Bump the python-minor-and-patch group with 3 updates |
| [110](00110.md) | PR | merged | Dependabot: ignore the actions OIO pins in issue-triage.yml |
| [109](00109.md) | PR | merged | ABA builds app code only: narrow its contract and policy |
| [108](00108.md) | Issue | closed | V2 composer: Ask becomes Follow-up, pill slider, sent-question strip |
| [107](00107.md) | Issue | closed | Retire old /map page, serve v2 map |
| [106](00106.md) | Issue | closed | V2: single navigation, retire legacy text menu drawer |
| [105](00105.md) | Issue | closed | V2: visible Listen button and vertical tour controls |
| [104](00104.md) | Issue | open | HANDOFF: Precedent v2 status, policies and open feedback queue (2026-10-18) |
| [103](00103.md) | Issue | open | V2 composer: Ask becomes Follow-up, New question reset, pill slider, remove Tour pill |
| [102](00102.md) | Issue | open | Retire the legacy /map page: /map serves the v2 map experience |
| [101](00101.md) | Issue | closed | V2 one navigation: icon rail is the only menu (retire legacy text drawer on v2) |
| [100](00100.md) | PR | merged | Memo citation links open the slim preview, not a new tab (#96 follow-up) |
| [99](00099.md) | PR | merged | V2 mobile single-pane: Answer vs Map, top panels, slim preview (#96) |
| [98](00098.md) | PR | merged | V2 tour narration flow and skip-to-stop (#95) |
| [97](00097.md) | PR | merged | V2 logo/icons refresh and sidebar routing to current pages |
| [96](00096.md) | Issue | closed | V2 mobile single-pane: Answer vs Map toggle, panels reuse the same pane |
| [95](00095.md) | Issue | closed | V2 tour narration flow and skip-to-stop |
| [94](00094.md) | Issue | closed | V2 logo/icons refresh and sidebar routing to current pages |
| [93](00093.md) | PR | merged | Serve v2 at root, keep v1 at /v1 (#92) |
| [92](00092.md) | Issue | closed | Serve v2 at root, keep v1 at /v1 |
| [91](00091.md) | PR | merged | Build v2 frontend (minimal, map-centric) at /v2 (#89) |
| [90](00090.md) | PR | closed | Bump actions/setup-python from 5 to 7 |
| [89](00089.md) | Issue | closed | Build v2 frontend (minimal, map-centric) at arize-v2.design-bakery.com |
| [88](00088.md) | PR | merged | Frontend inventory and Read first links for agents |
| [87](00087.md) | Issue | closed | Frontend inventory + agent discoverability |
| [86](00086.md) | Issue | open | [ISSUE]: UI cleanup: /slides on small screens, and slides.marketing.html uses the Tailwind CDN |
| [85](00085.md) | Issue | open | [ISSUE]: UI cleanup: map card and /map break on small screens (overlaps, legend, controls, 0 counties) |
| [84](00084.md) | PR | merged | One collapsible sidebar for navigation on every page |
| [83](00083.md) | PR | merged | CI audits the Pro's Python 3.9 pins and stops flagging SDK calls in tests |
| [82](00082.md) | Issue | closed | [ISSUE]: CI misses the Pro's Python 3.9 advisories and warns about SDK calls in test fixtures |
| [81](00081.md) | PR | closed | Bump the python-minor-and-patch group across 1 directory with 3 updates |
| [80](00080.md) | PR | closed | Bump actions/checkout from 4 to 7 |
| [79](00079.md) | PR | merged | Bump actions/dependency-review-action from 4 to 5 |
| [78](00078.md) | PR | merged | Bump actions/upload-artifact from 4 to 7 |
| [77](00077.md) | PR | merged | Bump actions/github-script from 7 to 9 |
| [76](00076.md) | PR | merged | CI checks the reuse-first rule and new dependencies, and pins them in a lock |
| [75](00075.md) | Issue | closed | [ISSUE]: The reuse-first rule and new dependencies are not checked in CI |
| [74](00074.md) | PR | merged | Agents reuse open-source tools before writing their own code |
| [73](00073.md) | Issue | closed | [ISSUE]: Agents have no written rule to reuse open-source tools before writing their own code |
| [72](00072.md) | PR | merged | Pages fit at 768 and 1024 px; CI runs the browser tests |
| [71](00071.md) | PR | merged | Audio tests: let headless Chromium finish clips |
| [70](00070.md) | PR | merged | Citation cards: readable type and jurisdiction, no dead links |
| [69](00069.md) | PR | merged | Observability in plain words: cards, simple charts, filters |
| [68](00068.md) | PR | merged | Dashboard loads on macOS: /api/stack works without /proc |
| [67](00067.md) | Issue | closed | [ISSUE]: Slow memo clip stalls after starting and never finishes, so the tour never starts |
| [66](00066.md) | PR | merged | Close linked issues even when auto-merge does the merge |
| [65](00065.md) | PR | merged | Tour starts at stop 1 after the memo; stops in [n] order; ?v=ts1 |
| [64](00064.md) | Issue | closed | [ISSUE]: Guided tour skips stop 1: home feed re-shows the run with cut passages and order() drops [1] |
| [63](00063.md) | PR | merged | Health lists only reachable voice providers (#32) |
| [62](00062.md) | Issue | open | [ISSUE]: UI cleanup: map citation popup and tour caption overlap the pins and tour controls |
| [61](00061.md) | Issue | closed | [ISSUE]: UI cleanup: citation cards show 'unknown' and a bare '20 CFR' with no passage |
| [60](00060.md) | PR | merged | Close linked issues after merge and tick off the UI cleanup tracker |
| [59](00059.md) | PR | merged | First screen cues + responsive 360–1440 on every page; ?v=ux1 |
| [58](00058.md) | Issue | open | [ISSUE]: UI cleanup: tracking issue |
| [57](00057.md) | Issue | closed | [ISSUE]: UI cleanup: every page works at 360, 390, 768, 1024 and 1440 px |
| [56](00056.md) | Issue | closed | [ISSUE]: UI cleanup: redesign Observability as a plain-language dashboard |
| [55](00055.md) | Issue | open | [ISSUE]: UI cleanup: remove the partner and pipeline sections from the sidebar |
| [54](00054.md) | Issue | open | [ISSUE]: UI cleanup: remove the voice and hands-free section from the sidebar |
| [53](00053.md) | Issue | open | [ISSUE]: UI cleanup: separate Run History page at /runs |
| [52](00052.md) | Issue | open | [ISSUE]: UI cleanup: /map tour controls, overlaps, duplicate summary and honest location stats |
| [51](00051.md) | Issue | open | [ISSUE]: UI cleanup: cut visible text and move detail into collapsibles |
| [50](00050.md) | Issue | closed | [ISSUE]: UI cleanup: one collapsible sidebar replaces the navbar menu |
| [49](00049.md) | Issue | open | [ISSUE]: UI cleanup: make / a chat-style page with an obvious first action |
| [48](00048.md) | PR | merged | Red-team UX/flows only — drop security suite |
| [47](00047.md) | Issue | closed | [ISSUE]: red-team: Missing theme CSS 404 on every page (broken styling asset) |
| [46](00046.md) | Issue | closed | [ISSUE]: red-team: Map Previous-stop and Mute controls often appear dead to first-time users |
| [45](00045.md) | Issue | closed | [ISSUE]: red-team: Observability All/Judged/Live and Next controls look unresponsive |
| [44](00044.md) | Issue | closed | [ISSUE]: red-team: Ask with empty input is a silent no-op (no validation message) |
| [43](00043.md) | Issue | closed | [ISSUE]: red-team: Mobile home has horizontal overflow — first screen not phone-ready |
| [42](00042.md) | Issue | closed | [ISSUE]: red-team: Navbar Dashboards link lands on a broken /dashboard (500 / JSON parse) |
| [41](00041.md) | PR | merged | Pin OIO and automate red-team finding issues |
| [40](00040.md) | Issue | open | [ISSUE]: red-team: tracking — automated red-team findings |
| [39](00039.md) | Issue | closed | [ISSUE]: red-team: GET /api/acs/events is public |
| [38](00038.md) | Issue | open | [ISSUE]: red-team: Safeguard FAIL still returns the answer to the client |
| [37](00037.md) | Issue | open | [ISSUE]: red-team: Anthropic fallback disabled on live (InferHub-only before template) |
| [36](00036.md) | Issue | open | [ISSUE]: red-team: SurrealDB down with silent networkx fallback (no user banner) |
| [35](00035.md) | Issue | open | [ISSUE]: red-team: Safeguard ignores uncited material claims |
| [34](00034.md) | Issue | open | [ISSUE]: red-team: Map locate() silently pins unknown courts to Denver |
| [33](00033.md) | Issue | closed | [ISSUE]: red-team: Missing static/theme/precedent-theme.css (404) |
| [32](00032.md) | Issue | closed | [ISSUE]: red-team: Health advertises kokoro in tts[] while kokoro=false |
| [31](00031.md) | Issue | closed | [ISSUE]: red-team: /api/stack 500 on macOS host (no /proc) |
| [30](00030.md) | Issue | closed | [ISSUE]: red-team: Oversized /api/ask JSON body accepted |
| [29](00029.md) | Issue | closed | [ISSUE]: red-team: Tour prefetch stores raw HTML in step text |
| [28](00028.md) | Issue | closed | [ISSUE]: red-team: XSS risk in map3d.js pinTags refs innerHTML |
| [27](00027.md) | Issue | closed | [ISSUE]: red-team: XSS sink in static/voice.js caption() |
| [26](00026.md) | Issue | closed | [ISSUE]: red-team: GET /api/run/{rid} creates directories for arbitrary ids |
| [25](00025.md) | Issue | closed | [ISSUE]: red-team: Ask rate limit bypass via client X-Forwarded-For |
| [24](00024.md) | Issue | closed | [ISSUE]: red-team: /api/sponsor leaks ARIZE_SPACE_ID |
| [23](00023.md) | Issue | closed | [ISSUE]: red-team: POST /api/claim and /api/release are unauthenticated |
| [22](00022.md) | Issue | closed | [ISSUE]: red-team: POST /api/acs/reload is unauthenticated |
| [21](00021.md) | PR | merged | Memo plays to the end before the tour; no timer advances a playing clip |
| [20](00020.md) | Issue | open | CI/CD: auto-deploy after merge (AUTOMERGE_TOKEN) + pin dependencies |
| [19](00019.md) | PR | merged | Tour waits for summary (no repeated stop 1) + featured demo run for new visitors |
| [18](00018.md) | PR | merged | tests: live JS check sends a User-Agent |
| [17](00017.md) | PR | merged | Move the backend into app/ and add a repo manifest, agent contracts and writing-helper pin |
| [16](00016.md) | PR | merged | Octo-backed LLM answer + retrieval caches (migration 0003), stale-answer purge, Fish timeout 5s |
| [15](00015.md) | PR | merged | Sequential audio queue: voice-overs never cut off |
| [14](00014.md) | PR | merged | deploy: merged-changes guard + confirmed reset input |
| [13](00013.md) | PR | merged | API contracts: pydantic models, committed OpenAPI, drift check |
| [12](00012.md) | PR | merged | CI gates: ruff lint + format check + mypy |
| [11](00011.md) | PR | merged | Robust TTS: Fish -> Kokoro -> browser, generation queue + tour prefetch, Octo-backed clip cache, versioned schema |
| [10](00010.md) | PR | merged | deploy: dedupe uncommitted-changes patches |
| [9](00009.md) | PR | merged | Audio loading indicator for TTS + sound on by default |
| [8](00008.md) | PR | merged | README: CI badge |
| [7](00007.md) | PR | merged | CI/CD pipeline, auto-merge, Pro deploy, ACS hot-loader |
| [6](00006.md) | Issue | open | CI/CD pipeline, auto-merge, ACS hot-loader, PDD hardening |
| [5](00005.md) | PR | merged | InferHub: no more empty answers from reasoning models; Octo timeout 5s |
| [4](00004.md) | PR | merged | Fail fast with 'data not loaded' when graph data is missing (no more hung runs) |
| [3](00003.md) | PR | merged | Add SEO: meta tags, OG share card, JSON-LD, robots.txt, sitemap.xml |
| [2](00002.md) | PR | merged | Clean up backup files, env-configurable graph data path, rewrite README |
| [1](00001.md) | Issue | open | Hosting: serve arize.design-bakery.com from the Daytona sandbox (tunnel keeps dropping) |
