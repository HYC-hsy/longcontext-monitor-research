# Multipart diagnostic ZIP

The public diagnostic ZIP was 226,462,321 bytes, above GitHub's single-file limit. Its three `.partNNN` files are consecutive, unmodified byte ranges of that ZIP. The external JSON index records each part's byte count and SHA-256, the reconstructed ZIP's byte count and SHA-256, and the hashes of all 271 ZIP members.

Concatenate `part001`, `part002`, and `part003` in numeric order into a file named `PMA_REMINDER_TOOL_3BBE_FIVE_ATTEMPTS_20261116.zip`. Verify its SHA-256 equals `005bf01f2f8b085aa0d6be9b14ac481b9331fe76aab1d10aca58dfa45c8c213c` before opening it. ZIP CRC and member hashes were checked locally and are checked again after remote readback.

The ZIP is a redacted visible projection, not raw HTTP bytes. Private originals remain on the Windows host. The second through fifth slots are retained as engineering failures; `ENGINEERING_FAILURE_AND_CLEANUP.md` distinguishes in-run cleanup from later removal of task-owned volumes.
