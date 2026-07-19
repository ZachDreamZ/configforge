import urllib.request

diagram = """flowchart TD
    A["Layer (dict source)"] --> C["forge()"]
    B["Layer (json file)"] --> C
    E["env (APP__*)"] --> C
    F["secrets (Fernet)"] --> C
    C --> D["deep merge"]
    D --> G["validate(schema)"]
    G --> H["Config"]
    D -.->|"scalar clash"| I["MergeConflictError"]"""

req = urllib.request.Request(
    "https://kroki.io/mermaid/png",
    data=diagram.encode("utf-8"),
    headers={"Content-Type": "text/plain"},
)
resp = urllib.request.urlopen(req)
with open("D:\\workspace\\configforge\\assets\\architecture.png", "wb") as f:
    f.write(resp.read())
print(f"Saved {resp.status}")
