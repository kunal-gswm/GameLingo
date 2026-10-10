with open("src/gamelingo/app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Let's just find `(u.file_id, "default", u.file_id, "json", "", 0, time.time()),`
# and replace it. But we also need to add the `rel = ` line.
old_str = """
    with conn:
        for u in units:
            conn.execute(
                "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u.file_id, "default", u.file_id, "json", "", 0, time.time()),
            )
"""
new_str = """
    with conn:
        for u in units:
            rel = f"data/{u.file_id}" if (game_path / "data" / u.file_id).exists() else f"www/data/{u.file_id}"
            conn.execute(
                "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u.file_id, "default", rel, "json", "", 0, time.time()),
            )
"""
if old_str.strip() in text:
    print("Found! Replacing.")
else:
    print("Not found! Regex needed.")

text = text.replace(old_str.strip(), new_str.strip())
with open("src/gamelingo/app.py", "w", encoding="utf-8") as f:
    f.write(text)
