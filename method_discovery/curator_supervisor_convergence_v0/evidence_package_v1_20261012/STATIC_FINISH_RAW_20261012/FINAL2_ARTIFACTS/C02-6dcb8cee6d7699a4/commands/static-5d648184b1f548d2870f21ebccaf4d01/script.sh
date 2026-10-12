python3 -c 'import hashlib,itertools,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); rows=[]; incomplete=False
if not root.is_dir(): sys.exit(2)
for index,path in enumerate(itertools.islice(root.rglob("*"),501)):
 if index>=500: incomplete=True; break
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
rows.sort()
print(json.dumps({"files":rows,"incomplete":incomplete},sort_keys=True))
' /tmp/absent_check
