import pathlib
p = pathlib.Path('synapse/server/dashboard.html')
content = p.read_text(encoding='utf-8')
subs = {
    '⚡': '&#9889;',
    '🔒': '&#128274;',
    '🔓': '&#128275;',
    '🚀': '&#128640;',
    '🧠': '&#129504;',
    '📄': '&#128196;',
    '📘': '&#128216;',
    '⬡': 'SYN',
    '✓': 'OK',
    '⚠': 'WARN'
}
for k, v in subs.items():
    content = content.replace(k, v)
content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
p.write_text(content, encoding='utf-8')
