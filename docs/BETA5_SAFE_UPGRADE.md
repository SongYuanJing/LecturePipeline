# Safe beta.4 → beta.5 upgrade

These steps are for a later, separately authorized update of an existing installation. Do not run them while workers are processing a lecture.

1. Confirm Windows 11 x64, adequate free space (at least 15 GiB for a clean install), and the published Setup.exe SHA-256 against its release checksum. Keep the accepted beta.4 installer and a working recovery copy available.
2. Record the current version, course paths, queue status and worker state. Stop the existing Lecture and Dialogue workers through their normal controls and verify they have exited. Close both GUI windows. Do not disable or rename existing Task Scheduler jobs as a substitute for stopping them.
3. Back up the **entire installation directory and its separate data directory** before upgrading. Include `config/config.json`, the vocabulary XLSX, course states, AI queue, Raw/SRT/Word results, and external course folders when those contain user files. Verify the backup can be read and that file hashes or a backup inventory were saved.
4. Run the downloaded product Setup.exe with the current installation and data paths, for example:

   ```powershell
   .\Setup.exe --upgrade --install "<existing-install>" --data "<existing-data>" --mode auto
   ```

   Choose the existing beta.4 installation. Setup refuses another source version or a mismatched data root. Do not point it at a DEV test installation or a new empty directory.
5. Wait for Setup to finish its first WebView2 initialization check. Only `status=updated` after the ready acknowledgement counts as success. Check that the installed version is `2.0.0-beta.5`, open both the WebView2 and Tk launchers, then compare the recorded courses, paths, queue IDs, processed lectures and vocabulary. Verify managed shortcuts point to the new version. Start the usual workers only after these checks.
6. If first launch fails, Setup automatically restores beta.4 using the recovery journal. Verify its version pointer and data before restarting workers. If a later issue requires manual rollback, stop the workers and both GUIs, restore from the verified backups, or use the specific `backup` directory recorded by Setup with the installed helper:

   ```powershell
   & "<existing-install>\runtime\asr\python.exe" -B "<existing-install>\launcher\safe_upgrade.py" rollback --install "<existing-install>" --backup "<recorded-safe-upgrade-backup>"
   ```

   The helper rejects a backup outside that installation and a version mismatch. Keep the data directory intact; investigate before any manual replacement.

The beta.4 **Update.cmd** path requires a code-only manifest that is intentionally absent from the beta.5 release materials. Use the full Setup.exe upgrade path.
