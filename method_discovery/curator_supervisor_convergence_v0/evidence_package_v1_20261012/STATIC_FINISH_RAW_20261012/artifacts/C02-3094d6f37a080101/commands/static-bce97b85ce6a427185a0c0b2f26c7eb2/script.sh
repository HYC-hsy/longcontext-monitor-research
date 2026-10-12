python3 -c 'import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); rows=[]; incomplete=False
if not root.is_dir(): sys.exit(2)
for path in sorted(root.rglob("*")):
 if len(rows)>=500: incomplete=True; break
 if path.is_symlink(): incomplete=True; continue
 if not path.is_file(): continue
 try:
  size=path.stat().st_size
  if size>4194304: incomplete=True; continue
  h=hashlib.sha256()
  with path.open("rb") as stream:
   for chunk in iter(lambda:stream.read(65536),b""): h.update(chunk)
  rows.append([path.relative_to(root).as_posix(),size,h.hexdigest()])
 except OSError: incomplete=True
print(json.dumps({"files":rows,"incomplete":incomplete},sort_keys=True))
' /tmp/go_check
