import re
from app.services.canonical import content_hash

NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)(?:\.)?\s+([A-Za-z][^\n]*)$")
UNITS = re.compile(r"^(?:seconds?|minutes?|mmHg|cycles?|measurement|percent|hours?|days?)\b", re.I)
LIST = re.compile(r"^(?:[•●\-]|\d+[.)])\s+")
CLASSIFICATIONS = ('Normal', 'Elevated', 'Hypertension Stage 1', 'Hypertension Stage 2', 'Hypertensive Crisis')


def parse_hierarchy(elements: list[dict]) -> tuple[list[dict], str]:
    nodes, by_number = [], {}
    title_lines = []
    current = None
    sizes = sorted(e.get('font_size',0) for e in elements if e.get('font_size',0)>0)
    body_size = sizes[len(sizes)//2] if sizes else 11
    for e in elements:
        if e['kind']=='repeated_header':
            continue
        text = e['text']
        match = NUMBERED.fullmatch(text) if e['kind']=='unclassified' else None
        heading = False
        if match:
            number, label = match.groups()
            numbered_list = label.startswith(CLASSIFICATIONS) or ('.' not in number and LIST.match(text) and not (e.get('bold') or e.get('font_size',0)>body_size+.5))
            heading = not numbered_list and not UNITS.match(label) and len(text)<150 and ('.' in number or e.get('bold') or e.get('font_size',0)>body_size+.5)
        if heading:
            number,label = match.groups()
            parts = number.split('.')
            parent = None
            for length in range(len(parts)-1,0,-1):
                candidate = '.'.join(parts[:length])
                if candidate in by_number:
                    parent = by_number[candidate]
                    break
            warnings = []
            if len(parts)>1 and (parent is None or parent['section_number'] != '.'.join(parts[:-1])):
                warnings.append('missing intermediate numbered ancestor; attached to nearest existing ancestor')
            if number in by_number:
                warnings.append('duplicate section number; identity requires review')
            current = dict(heading=label, section_number=number, declared_level=len(parts), effective_level=parent['effective_level']+1 if parent else 1, parent_index=parent['order_index'] if parent else None, order_index=len(nodes), elements=[{**e,'kind':'heading'}], warnings=warnings)
            nodes.append(current)
            by_number[number] = current
        elif not nodes and e['kind']=='unclassified' and (e.get('bold') or e.get('font_size',0)>body_size+.5):
            title_lines.append(text)
            # Title retained as source evidence in the preamble node too.
            if current is None:
                current = dict(heading='Preamble',section_number=None,declared_level=0,effective_level=0,parent_index=None,order_index=len(nodes),elements=[],warnings=[])
            current['elements'].append({**e,'kind':'title'})
        else:
            if current is None:
                current = dict(heading='Preamble',section_number=None,declared_level=0,effective_level=0,parent_index=None,order_index=len(nodes),elements=[],warnings=[])
            kind = e['kind']
            if kind=='unclassified':
                kind = 'list_item' if LIST.match(text) or text.startswith(CLASSIFICATIONS) else 'paragraph'
                if '|' in text:
                    kind = 'unclassified'
                    current['warnings'].append('possible unruled table; raw line retained, structure uncertain')
            current['elements'].append({**e,'kind':kind})
        # Flush preamble before the first heading without disturbing indices.
        if heading and title_lines and len(nodes)==1 and current is nodes[0]:
            pass
    # The preamble is separate from sections; source title lines are accounted below.
    assigned = {e['element_id'] for n in nodes for e in n['elements']}
    preamble = [dict(e,kind='title' if e['text'] in title_lines else e['kind']) for e in elements if e['kind']!='repeated_header' and e['element_id'] not in assigned]
    if preamble:
        nodes.append(dict(heading='Preamble',section_number=None,declared_level=0,effective_level=0,parent_index=None,order_index=len(nodes),elements=preamble,warnings=['unnumbered preamble retained separately']))
    for n in nodes:
        body = []
        for e in n['elements']:
            if e['kind']=='heading':
                continue
            if e['kind']=='paragraph' and body and body[-1][0]=='paragraph':
                body[-1] = ('paragraph', body[-1][1]+' '+e['text'])
            else:
                body.append((e['kind'],e['text']))
        n['body_text'] = '\n'.join(t for _,t in body)
        n['content_hash'] = content_hash(n['heading'],[e for e in n['elements'] if e['kind']!='heading'])
        n['page_start'] = min(e['page'] for e in n['elements'])
        n['page_end'] = max(e['page'] for e in n['elements'])
        if n['section_number']=='8.1' and len(n['body_text'])<40:
            n['warnings'].append('possibly truncated classification content; manual review required')
    return nodes, ' '.join(title_lines) or 'Untitled PDF'
