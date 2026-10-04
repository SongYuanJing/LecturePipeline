# Phase 1c architecture decision — accepted 2026-10-04

The owner selected **self-contained .NET 10 x64 WinForms**, with **Windows 11 x64**
as the initial official support target. Windows 10 is not a supported product
platform yet. The comparison below records the rationale at decision time;
implementation and validation are documented in [PHASE_1C.md](PHASE_1C.md).

## Common boundary

The bootstrap executable should own only the pre-Python steps: select a writable
install/data location, fetch an approved release manifest and the private base
runtime, validate identity/hashes, stage/extract, then hand off to the existing
component/setup code. It must not install a system Python or alter global PATH.
Model/CUDA download and ASR policies remain shared with the application; do not
create a second, incompatible dependency resolver. No own web server is needed.

Use tagged GitHub Releases, never `main`. Keep the initial bootstrap distribution
and updater contracts compatible, but do not implement Phase 2 opportunistically.
Authenticity/signing, interruption recovery, byte progress and cancellation at
safe transaction boundaries require explicit acceptance criteria in Phase 1c.

## Comparison

Size figures are planning orders of magnitude for the bootstrap shell only,
NOT measurements or total application/model sizes. Measure a prototype after
the architecture decision. The same multi-GB model/CUDA payload remains separate.

| Dimension | Minimal native EXE: C++/Win32 | Self-contained .NET 10 / WinForms | PowerShell 5.1 based |
| --- | --- | --- | --- |
| Fresh-machine dependencies | Win32/WinHTTP/crypto APIs; statically link C runtime if avoiding separate VC install for the shell. ZIP support must be chosen explicitly. ASR still has its own prerequisites. | Include .NET runtime with `win-x64` publish; user needs neither Python nor preinstalled .NET Desktop Runtime. Publish/test any required native extraction behavior. | Windows PowerShell 5.1 and the OS .NET Framework/WPF or WinForms. No Python for the first download, but script policy/host availability are dependencies. |
| Bootstrap download size | Typically low single-digit MB for a restrained Win32 shell; more if frameworks are introduced. | Tens of MB to roughly 100+ MB with desktop runtime, depending on publish choices. Do not assume trimming works safely with reflection/UI libraries without testing. | Script/launcher usually KB to sub-MB; wrapping a script in EXE does not remove its PowerShell dependency. |
| GUI and maintenance | Good Windows-native controls; most custom work for layout, async state, accessibility and localization. | Best development cost for a conventional Windows wizard: mature controls, async HTTP and cancellation APIs. | Adequate for an internal tool; UI thread/runspace coordination and packaging produce more operational friction. |
| Progress/cancel/retry | Fully possible with WinHTTP + explicit worker/state machine; highest low-level implementation burden. | HTTP streaming, progress reporting and cancellation tokens fit naturally. Retries still need bounds; cancel must preserve verified files and avoid half-published state. | Possible with runspaces/.NET HTTP APIs, but not by blocking UI with Invoke-WebRequest. Error propagation and child termination require care. |
| SmartScreen/AV | Sign + timestamp; small native EXE is not automatically trusted. Avoid opaque packers/self-modifying launchers. | Sign + timestamp; self-contained/single-file does not bypass reputation or guarantee no AV false positives. | Downloaded scripts, execution policy, AMSI and enterprise controls add friction. Do not change machine policy or rely on policy bypass as product architecture. |
| Updating | Versioned signed shell/base payload; replacing running EXE needs an explicit deferred/side-by-side mechanism. | Same; bundled .NET security updates require publishing a new shell, not relying on user's global .NET updates. | Easy to replace scripts, but signature/integrity and policy controls still apply; never execute an unverified remotely fetched script. |
| GitHub Actions | Windows runner + pinned MSVC/SDK/CMake configuration; test artifact, sign in a protected release job. | Windows runner + pinned .NET SDK/global.json; `dotnet publish` self-contained; test and sign release artifact. Straightforward standard pipeline. | Windows runner + Pester/static checks; sign scripts, package and test execution under realistic policies. Host defaults must be explicit. |
| Windows 10/11 | Can target both x64 with a deliberate minimum API set; supported OS editions/lifecycle and ASR native stack still need a test matrix. | .NET 10 current support matrix covers supported Windows 11 and listed Windows 10 LTSC/Enterprise editions. Do not promise vendor support for every Windows 10 installation. | Built-in 5.1 is available on these Windows generations, but that alone is not a product support guarantee. Policies and OS servicing status vary. |

Microsoft documents [self-contained single-file deployment](https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview)
and the current [Windows/.NET support matrix](https://learn.microsoft.com/en-us/dotnet/core/install/windows).
In particular, support and technical runnability on an old Windows 10 edition
are different claims; the current matrix limits Windows 10 support to listed
LTSC/Enterprise editions. The application itself currently documents tested
Windows 11 x64, not a completed Windows 10 qualification.

[SmartScreen reputation guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
explains why signing is important but does not guarantee a warning-free first
download; EV certificates do not provide an automatic reputation bypass.
[PowerShell execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1)
and organizational policy constraints must be respected.
GitHub provides an official [.NET Actions workflow guide](https://docs.github.com/en/actions/tutorials/build-and-test-code/net).

## Recommendation for this project

Prefer a **self-contained .NET 10 x64 WinForms bootstrapper** if the owner accepts
a bootstrap download in the tens-of-MB range. This is an engineering judgment:
for this project, understandable installation/progress/retry UI and maintainable
Windows code matter more than saving those MB next to the large model payload.
It avoids making a fresh-machine user install .NET or Python manually.

Use a minimal native EXE if a strict small-download requirement outweighs the
additional native development/testing cost. Keep PowerShell as a developer or
diagnostic route, not the primary end-user installation experience.

The accepted sequence was prototype size/startup measurement followed by the
full flow. Windows 10 qualification and Phase 2 updater remain separate work.
