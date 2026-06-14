import re

with open('c:/Users/johnj/Desktop/dreamweave/frontend/dreamweave.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Clean graph nodes mock data
graph_nodes_mock = re.compile(r'let graphNodes = \[\s*\{ id: 0, label: \'Misinformation.*?\];', re.DOTALL)
content = graph_nodes_mock.sub('let graphNodes = [];', content)

graph_edges_mock = re.compile(r'let graphEdges = \[.*?\];', re.DOTALL)
content = graph_edges_mock.sub('let graphEdges = [];', content)

conflict_edges_mock = re.compile(r'let conflictEdges = \[.*?\];')
content = conflict_edges_mock.sub('let conflictEdges = [];', content)

# 2. Clean node popups mock data
node_popup_mock = re.compile(r'const descriptions = \{.*?\};\s*const desc = descriptions\[node\.label\] \|\| \'A concept in the knowledge graph\.\';', re.DOTALL)
content = node_popup_mock.sub('const desc = node.label + " - Part of the knowledge graph.";', content)

# 3. Clean random chunk numbers in sources
sources_chips_mock = r"const layers=['L1 · Chunk #'+Math.ceil(Math.random()*20),'L1 · Chunk #'+Math.ceil(Math.random()*10),'L2 · Relationship','L3 · Pattern'];return`<div class=\"source-chip\"><div class=\"sc-name\">${s}</div><div class=\"sc-meta\">${layers[i%4]}</div></div>`"
sources_chips_real = r"return`<div class=\"source-chip\"><div class=\"sc-name\">${s}</div><div class=\"sc-meta\">L1 Source</div></div>`"
content = content.replace(sources_chips_mock, sources_chips_real)

# 4. Make card generate in the middle / slowly
# In renderAnswer, we have `ab.appendChild(metaDiv);` directly before the formatting block.
# We will wrap it in a setTimeout, and give metaDiv a class for fading in.

render_answer_old = r"""  // Append retrieval summary and sources after answer text
  const metaDiv = document.createElement('div');"""

render_answer_new = r"""  // Append retrieval summary and sources slowly
  const metaDiv = document.createElement('div');
  metaDiv.style.opacity = '0';
  metaDiv.style.transition = 'opacity 1s ease-in-out';
  metaDiv.style.marginTop = '16px';"""

content = content.replace(render_answer_old, render_answer_new)

append_meta_old = r"""  ab.appendChild(metaDiv);

  const rawAnswer = data.answer;"""

append_meta_new = r"""  const rawAnswer = data.answer;"""

content = content.replace(append_meta_old, append_meta_new)

# Now, we need to append metaDiv at the end of typing, or in the middle.
# Let's append it at the end, fading in.

type_char_old = r"""      if (charIndex < fullText.length) {
        answerEl.textContent = fullText.substring(0, charIndex + 1);
        charIndex++;
        // Only auto-scroll if user hasn't manually scrolled up
        if (!userScrolled) chat.scrollTop = chat.scrollHeight;
        setTimeout(typeChar, 18);
      } else {
        chat.removeEventListener('scroll', scrollGuard);
      }"""

type_char_new = r"""      if (charIndex < fullText.length) {
        answerEl.textContent = fullText.substring(0, charIndex + 1);
        charIndex++;
        
        // Show metaDiv midway through typing
        if (charIndex === Math.floor(fullText.length / 2)) {
          ab.appendChild(metaDiv);
          // Trigger reflow
          void metaDiv.offsetWidth;
          metaDiv.style.opacity = '1';
        }
        
        // Only auto-scroll if user hasn't manually scrolled up
        if (!userScrolled) chat.scrollTop = chat.scrollHeight;
        setTimeout(typeChar, 18);
      } else {
        // Fallback in case string is very short
        if (!ab.contains(metaDiv)) {
          ab.appendChild(metaDiv);
          void metaDiv.offsetWidth;
          metaDiv.style.opacity = '1';
        }
        chat.removeEventListener('scroll', scrollGuard);
      }"""

content = content.replace(type_char_old, type_char_new)

# For formatted (isHtml), we also need to append it
formatted_html_old = r"""    // Render structured HTML immediately, no typing effect needed
    answerEl.innerHTML = formatted.html;
    if (!userScrolled) chat.scrollTop = chat.scrollHeight;
    chat.removeEventListener('scroll', scrollGuard);"""

formatted_html_new = r"""    // Render structured HTML immediately, no typing effect needed
    answerEl.innerHTML = formatted.html;
    ab.appendChild(metaDiv);
    void metaDiv.offsetWidth;
    metaDiv.style.opacity = '1';
    if (!userScrolled) chat.scrollTop = chat.scrollHeight;
    chat.removeEventListener('scroll', scrollGuard);"""

content = content.replace(formatted_html_old, formatted_html_new)


with open('c:/Users/johnj/Desktop/dreamweave/frontend/dreamweave.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Success.')
