from difflib import SequenceMatcher


def match_nodes(nodes: list[dict], previous: list) -> list[tuple[object | None, dict]]:
    """One-to-one matching. Ambiguity produces a new identity and visible evidence."""
    results, used = [], set()
    for node in nodes:
        parent_number = nodes[node['parent_index']]['section_number'] if node['parent_index'] is not None else None
        def context(old):
            parent = next((r for r in previous if r.id==old.parent_revision_id),None)
            return parent.section_number if parent else None
        exact = [r for r in previous if r.id not in used and r.section_number==node['section_number'] and context(r)==parent_number]
        if len(exact)==1:
            old = exact[0]
            evidence = {'method':'number_and_parent','confidence':1.0}
        else:
            scores = []
            for r in previous:
                if r.id in used:
                    continue
                title = SequenceMatcher(None,r.heading.lower(),node['heading'].lower()).ratio()
                body = SequenceMatcher(None,r.body_text,node['body_text']).ratio() if r.body_text and node['body_text'] else 0
                score = .45*title+.55*body
                if score>=.83:
                    scores.append((score,r))
            scores.sort(key=lambda x:(-x[0],x[1].id))
            if len(exact)>1 or (len(scores)>1 and scores[0][0]-scores[1][0]<.08):
                old=None
                evidence={'method':'ambiguous','candidate_logical_ids':sorted({r.logical_node_id for r in exact} | {r.logical_node_id for _,r in scores}), 'confidence':0}
                node['warnings'].append('ambiguous version match; new logical identity; review required')
            elif scores:
                old=scores[0][1]
                evidence={'method':'heading_body_similarity','confidence':scores[0][0]}
                node['warnings'].append('probable moved/renamed section match; review required')
            else:
                old=None
                evidence={'method':'new','confidence':1.0}
        if old:
            used.add(old.id)
        results.append((old,evidence))
    return results
