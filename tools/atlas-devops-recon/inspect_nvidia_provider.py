import json, pathlib
p=pathlib.Path.home()/".config"/"opencode"/"opencode.json"
if p.is_file():
 try:
  obj=json.loads(p.read_text(encoding="utf-8-sig"))
  for name,data in obj.get("provider",{}).items():
   print(json.dumps({"provider":name,"model_ids":list(data.get("models",{}))},ensure_ascii=True))
 except (ValueError,OSError) as e: print(type(e).__name__)
else: print("No explicit opencode.json provider config")
