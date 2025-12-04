from flask import Blueprint, render_template, request, Response, jsonify
from flask_login import login_required, current_user
from tools.baidu_crawler import crawl_baidu_news
from tools.baidu_crawler import crawl_xinhua_sc_news
from tools.baidu_crawler import deep_collect_content, collect_content_by_rule
import urllib.parse
from app import db
from app.models import CollectionItem, CrawlRule
import json

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    return render_template('index.html', title='首页')


@bp.route('/collector')
@login_required
def collector_page():
    return render_template('collector.html', title='数据采集管理')

@bp.route('/warehouse')
@login_required
def warehouse_page():
    return render_template('warehouse.html', title='数据仓库管理')

@bp.route('/rules')
@login_required
def rules_page():
    return render_template('rules.html', title='采集规则库')

@bp.route('/collector/stream')
@login_required
def collector_stream():
    keyword = request.args.get('keyword', '')
    max_count = request.args.get('count', default=20, type=int)
    source = request.args.get('source', default='baidu')

    def sse_event(data):
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        yield sse_event({"type": "start", "keyword": keyword, "total": max_count, "source": source})
        if source == 'xinhua':
            results = crawl_xinhua_sc_news(max_count=max_count)
        else:
            results = crawl_baidu_news(keyword, max_count=max_count)
        total = len(results)
        for idx, item in enumerate(results, 1):
            item_update = dict(item)
            item_update.update({"deep_collected": False})
            yield sse_event({"type": "item", "index": idx, "total": total, "item": item_update})
            yield sse_event({"type": "progress", "current": idx, "total": total})
        yield sse_event({"type": "complete", "total": total})

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }
    return Response(generate(), mimetype='text/event-stream', headers=headers)

@bp.route('/warehouse/list')
@login_required
def warehouse_list():
    page = request.args.get('page', default=1, type=int)
    size = request.args.get('size', default=20, type=int)
    keyword = request.args.get('keyword', default='', type=str)
    q = CollectionItem.query
    if keyword:
        q = q.filter(CollectionItem.title.like(f"%{keyword}%"))
    q = q.order_by(CollectionItem.created_at.desc())
    items = q.paginate(page=page, per_page=size, error_out=False)
    data = []
    for it in items.items:
        data.append({
            'id': it.id,
            'keyword': it.keyword,
            'title': it.title,
            'cover': it.cover,
            'url': it.url,
            'source': it.source,
            'deep_collected': it.deep_collected,
            'deep_content': it.deep_content,
            'created_at': it.created_at.isoformat()
        })
    return jsonify({
        'page': page,
        'size': size,
        'total': items.total,
        'items': data
    })

@bp.route('/warehouse/update', methods=['POST'])
@login_required
def warehouse_update():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    it = db.session.get(CollectionItem, int(id_))
    if not it:
        return jsonify({'error': 'not found'}), 404
    for k in ['keyword','title','cover','url','source','deep_collected','deep_content']:
        if k in payload:
            setattr(it, k, payload.get(k))
    db.session.commit()
    return jsonify({'id': it.id})

@bp.route('/warehouse/delete', methods=['POST'])
@login_required
def warehouse_delete():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    it = db.session.get(CollectionItem, int(id_))
    if not it:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(it)
    db.session.commit()
    return jsonify({'deleted': 1})

@bp.route('/warehouse/analyze', methods=['POST'])
@login_required
def warehouse_analyze():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    return jsonify({'status': 'pending', 'id': id_})

@bp.route('/rules/list')
@login_required
def rules_list():
    keyword = request.args.get('keyword', default='', type=str)
    q = CrawlRule.query
    if keyword:
        q = q.filter(CrawlRule.site.like(f"%{keyword}%"))
    q = q.order_by(CrawlRule.created_at.desc())
    items = q.all()
    data = []
    for r in items:
        data.append({
            'id': r.id,
            'site': r.site,
            'title_xpath': r.title_xpath,
            'content_xpath': r.content_xpath,
            'headers_json': r.headers_json,
            'created_at': r.created_at.isoformat()
        })
    return jsonify({'items': data})


def parse_headers_input(raw):
    if not raw:
        return None
    try:
        # If it's already valid JSON, just normalize it
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return json.dumps(parsed, ensure_ascii=False)
    except:
        pass
    
    # Treat as raw headers text
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    headers = {}
    current_key = None
    
    for line in lines:
        # Check for "Key: Value" or "Key:"
        if ':' in line:
            # If line starts with a key pattern (no spaces before colon usually)
            # Priority 1: Key: Value
            parts = line.split(':', 1)
            key = parts[0].strip()
            val = parts[1].strip()
            
            if not val:
                # Case: "Key:" (value on next line)
                current_key = key
            else:
                # Case: "Key: Value"
                headers[key] = val
                current_key = None
        else:
            # No colon, might be value for previous key
            if current_key:
                headers[current_key] = line
                current_key = None
            else:
                # Orphan line, ignore or treat as part of previous? 
                # For safety, ignore
                pass
                
    return json.dumps(headers, ensure_ascii=False)

@bp.route('/rules/create', methods=['POST'])
@login_required
def rules_create():
    payload = request.get_json() or {}
    try:
        h_in = payload.get('headers_json')
        h_json = parse_headers_input(h_in)
        
        r = CrawlRule(
            site=payload.get('site'),
            title_xpath=payload.get('title_xpath'),
            content_xpath=payload.get('content_xpath'),
            headers_json=h_json
        )
        db.session.add(r)
        db.session.commit()
        return jsonify({'id': r.id})
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({'error': 'create failed'}), 500

@bp.route('/rules/update', methods=['POST'])
@login_required
def rules_update():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(CrawlRule, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
        
    if 'site' in payload:
        r.site = payload.get('site')
    if 'title_xpath' in payload:
        r.title_xpath = payload.get('title_xpath')
    if 'content_xpath' in payload:
        r.content_xpath = payload.get('content_xpath')
    if 'headers_json' in payload:
        r.headers_json = parse_headers_input(payload.get('headers_json'))
        
    db.session.commit()
    return jsonify({'id': r.id})

@bp.route('/rules/delete', methods=['POST'])
@login_required
def rules_delete():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(CrawlRule, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'deleted': 1})

@bp.route('/rules/batch_delete', methods=['POST'])
@login_required
def rules_batch_delete():
    payload = request.get_json() or {}
    ids = payload.get('ids', [])
    if not ids:
        return jsonify({'deleted': 0})
    try:
        count = CrawlRule.query.filter(CrawlRule.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'deleted': count})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'delete failed'}), 500

@bp.route('/collector/deep', methods=['POST'])
@login_required
def collector_deep():
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({"error": "missing url"}), 400
    content = deep_collect_content(url)
    return jsonify({"deep_content": content, "deep_collected": True})

@bp.route('/warehouse/batch_deep', methods=['POST'])
@login_required
def warehouse_batch_deep():
    payload = request.get_json() or {}
    ids = payload.get('ids', [])
    if not ids:
        return jsonify({'processed': 0})
    
    items = CollectionItem.query.filter(CollectionItem.id.in_(ids)).all()
    processed = 0
    
    # Pre-fetch all rules to minimize DB queries? Or just query per item.
    # For robustness, query all rules and match in memory or query per domain.
    # Let's query per item to be simpler or load all rules. 
    # Since rules table is small, loading all is fine.
    all_rules = CrawlRule.query.all()
    
    for it in items:
        try:
            if not it.url:
                continue
                
            # Extract domain
            domain = urllib.parse.urlparse(it.url).netloc
            
            # Find matching rule
            matched_rule = None
            for r in all_rules:
                if r.site and r.site in domain:
                    matched_rule = r
                    break
            
            title = ""
            content = ""
            
            if matched_rule:
                # Use rule
                res = collect_content_by_rule(
                    it.url, 
                    matched_rule.title_xpath, 
                    matched_rule.content_xpath, 
                    matched_rule.headers_json
                )
                if res and (res[0] or res[1]):
                    title, content = res
            
            # Fallback if rule failed or no rule found
            if not content:
                # Use generic crawler
                content = deep_collect_content(it.url)
                # If generic works but we had a rule, it means rule is broken.
                # User asked to "auto update" if rule changed.
                # But we don't have the new XPath. We just save the content.
            
            if title:
                it.title = title # Update title if we got a better one from rule
            
            it.deep_content = content
            it.deep_collected = True
            processed += 1
            
        except Exception as e:
            print(f"Batch deep collect error for item {it.id}: {e}")
            continue
            
    db.session.commit()
    return jsonify({'processed': processed})

@bp.route('/collector/save', methods=['POST'])
@login_required
def collector_save():
    payload = request.get_json() or {}
    keyword = payload.get('keyword', '')
    items = payload.get('items', [])
    saved = 0
    for it in items:
        try:
            ci = CollectionItem(
                keyword=keyword,
                title=it.get('title'),
                cover=it.get('cover'),
                url=it.get('url'),
                source=it.get('source'),
                deep_collected=bool(it.get('deep_collected')),
                deep_content=it.get('deep_content')
            )
            db.session.add(ci)
            saved += 1
        except Exception:
            db.session.rollback()
            continue
    db.session.commit()
    return jsonify({"saved": saved})

@bp.route('/collector/save_one', methods=['POST'])
@login_required
def collector_save_one():
    payload = request.get_json() or {}
    keyword = payload.get('keyword', '')
    item = payload.get('item') or {}
    try:
        ci = CollectionItem(
            keyword=keyword,
            title=item.get('title'),
            cover=item.get('cover'),
            url=item.get('url'),
            source=item.get('source'),
            deep_collected=bool(item.get('deep_collected')),
            deep_content=item.get('deep_content')
        )
        db.session.add(ci)
        db.session.commit()
        return jsonify({"id": ci.id})
    except Exception:
        db.session.rollback()
        return jsonify({"error": "save failed"}), 500
