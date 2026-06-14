import re

with open('c:/Users/johnj/Desktop/dreamweave/frontend/dreamweave.html', 'r', encoding='utf-8') as f:
    content = f.read()

chat_start = content.find('    <!-- Chat area -->')
input_start = content.find('    <!-- Input area -->')

print(f'chat_start line: {content[:chat_start].count(chr(10)) + 1}')
print(f'input_start line: {content[:input_start].count(chr(10)) + 1}')

NEW_CHAT_SECTION = (
    '    <!-- Chat area -->\n'
    '    <div class="chat-area" id="chatArea">\n'
    '      <!-- Welcome state: shown until first real message is sent -->\n'
    '      <div id="welcomeState" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;opacity:0.5;">\n'
    '        <svg width="48" height="48" viewBox="0 0 28 28" fill="none">\n'
    '          <circle cx="14" cy="14" r="12" stroke="rgba(96,165,250,0.3)" stroke-width="1"/>\n'
    '          <circle cx="14" cy="14" r="8" stroke="rgba(167,139,250,0.4)" stroke-width="1" stroke-dasharray="3 5"/>\n'
    '          <circle cx="14" cy="14" r="4" stroke="rgba(52,211,153,0.4)" stroke-width="1"/>\n'
    '          <circle cx="14" cy="14" r="3" fill="rgba(52,211,153,0.6)"/>\n'
    '        </svg>\n'
    '        <div style="text-align:center;">\n'
    '          <div style="font-size:15px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;">DREAMWEAVE is ready</div>\n'
    '          <div style="font-size:12px;color:var(--text-muted);">Ask anything about your ingested knowledge</div>\n'
    '        </div>\n'
    '      </div>\n'
    '\n'
    '      <div class="typing-indicator" id="typingIndicator">\n'
    '        <div class="loading-dots"><span></span><span></span><span></span></div>\n'
    '        <span>DREAMWEAVE is thinking across layers\u2026</span>\n'
    '      </div>\n'
    '    </div>\n'
    '\n'
)

new_content = content[:chat_start] + NEW_CHAT_SECTION + content[input_start:]

with open('c:/Users/johnj/Desktop/dreamweave/frontend/dreamweave.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Done. Line count: {new_content.count(chr(10)) + 1}')
print('Verify chat area:')
idx = new_content.find('<!-- Chat area -->')
print(new_content[idx:idx+400])
