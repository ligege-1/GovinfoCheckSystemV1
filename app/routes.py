from flask import Blueprint, render_template, request, Response, jsonify
from flask_login import login_required, current_user
from tools.baidu_crawler import crawl_baidu_news
from tools.baidu_crawler import crawl_xinhua_sc_news
from tools.baidu_crawler import deep_collect_content, collect_content_by_rule
import urllib.parse
from app import db
from app.models import CollectionItem, CrawlRule, DeepCollectionContent, AiEngine
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

@bp.route('/ai_engines')
@login_required
def ai_engines_page():
    return render_template('ai_engines.html', title='AI引擎管理')

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
            results_gen = crawl_xinhua_sc_news(max_count=max_count)
        else:
            results_gen = crawl_baidu_news(keyword, max_count=max_count)
        
        count = 0
        for idx, item in enumerate(results_gen, 1):
            count = idx
            item_update = dict(item)
            item_update.update({"deep_collected": False})
            yield sse_event({"type": "item", "index": idx, "total": max_count, "item": item_update})
            yield sse_event({"type": "progress", "current": idx, "total": max_count})
        
        yield sse_event({"type": "complete", "total": count})

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }
    return Response(generate(), mimetype='text/event-stream', headers=headers)

from urllib.parse import urlparse

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
        # Retrieve deep content from new table or fallback to old field
        deep_content_val = ""
        if it.deep_content_obj:
            deep_content_val = it.deep_content_obj.content
        elif it.deep_content:
            deep_content_val = it.deep_content
            
        domain = ''
        if it.url:
            try:
                domain = urlparse(it.url).netloc
            except:
                pass

        data.append({
            'id': it.id,
            'keyword': it.keyword,
            'title': it.title,
            'cover': it.cover,
            'url': it.url,
            'source': it.source,
            'domain': domain,
            'rule_id': it.rule_id,
            'deep_collected': it.deep_collected,
            'deep_content': deep_content_val,
            'created_at': it.created_at.isoformat()
        })
    return jsonify({
        'page': page,
        'size': size,
        'total': items.total,
        'items': data
    })

@bp.route('/warehouse/auto_associate', methods=['POST'])
@login_required
def warehouse_auto_associate():
    try:
        rules = CrawlRule.query.all()
        items = CollectionItem.query.filter(CollectionItem.rule_id == None).all()
        count = 0
        
        for it in items:
            if not it.url or not it.source:
                continue
                
            domain = ''
            try:
                domain = urlparse(it.url).netloc
            except:
                continue
                
            # Logic: Domain + Source Name matches Rule(Domain + Name)
            # We assume Rule.site stores the domain or identifier, and Rule.name stores the name
            for r in rules:
                # Check if rule site matches domain (or part of it) AND rule name matches source
                # Using looser matching for robustness
                site_match = (r.site and (r.site == domain or r.site in domain or domain in r.site))
                name_match = (r.name and (r.name == it.source or r.name in it.source or it.source in r.name))
                
                if site_match and name_match:
                    it.rule_id = r.id
                    count += 1
                    break
        
        if count > 0:
            db.session.commit()
            
        return jsonify({'associated': count})
    except Exception as e:
        print(f"Auto associate error: {e}")
        return jsonify({'error': str(e)}), 500

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
    for k in ['keyword','title','cover','url','source','deep_collected']:
        if k in payload:
            setattr(it, k, payload.get(k))
            
    if 'deep_content' in payload:
        content = payload.get('deep_content')
        if it.deep_content_obj:
            it.deep_content_obj.content = content
        else:
            it.deep_content_obj = DeepCollectionContent(content=content)
            
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

@bp.route('/warehouse/batch_delete', methods=['POST'])
@login_required
def warehouse_batch_delete():
    payload = request.get_json() or {}
    ids = payload.get('ids', [])
    if not ids:
        return jsonify({'deleted': 0})
    try:
        # Using synchronize_session=False for bulk delete might require session expiry if objects are loaded,
        # but here we just want to delete.
        # Note: cascade delete should work if defined in models, but bulk delete with query.delete() might bypass SQLAlchemy cascades 
        # if not configured to fetch.
        # However, our model definition has:
        # deep_content_obj = db.relationship(..., cascade="all, delete-orphan")
        # Standard query.delete() emits DELETE SQL directly and might skip python-side cascades unless config is set.
        # For safety and correctness with cascades, we should iterate if the number is small, or ensure DB-level foreign key cascades are set.
        # In `app/models.py`, we defined foreign key, but did we set ON DELETE CASCADE in SQL?
        # Flask-SQLAlchemy/SQLAlchemy relationship cascade is Python-side usually unless passive_deletes=True.
        # Let's check models.py quickly to be sure about cascade behavior.
        # If I use `delete(synchronize_session=False)`, Python cascades won't run.
        # So deep content might be orphaned if I don't iterate.
        # Given the user wants "batch delete", performance is good but correctness is better.
        # Let's iterate for now to ensure deep content is also deleted via relationship cascade.
        
        items = CollectionItem.query.filter(CollectionItem.id.in_(ids)).all()
        count = 0
        for it in items:
            db.session.delete(it)
            count += 1
        db.session.commit()
        return jsonify({'deleted': count})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'delete failed'}), 500

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
        q = q.filter(
            (CrawlRule.site.like(f"%{keyword}%")) | 
            (CrawlRule.name.like(f"%{keyword}%"))
        )
    q = q.order_by(CrawlRule.created_at.desc())
    items = q.all()
    data = []
    for r in items:
        data.append({
            'id': r.id,
            'name': r.name,
            'site': r.site,
            'match_type': r.match_type,
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
            name=payload.get('name', '未命名规则'),
            site=payload.get('site'),
            match_type=payload.get('match_type', 'domain'),
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
        
    if 'name' in payload:
        r.name = payload.get('name')
    if 'site' in payload:
        r.site = payload.get('site')
    if 'match_type' in payload:
        r.match_type = payload.get('match_type')
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
    manual_rule_id = payload.get('rule_id') # Allow manual binding
    
    if not ids:
        return jsonify({'processed': 0})
    
    items = CollectionItem.query.filter(CollectionItem.id.in_(ids)).all()
    processed = 0
    
    # Load all rules for matching
    all_rules = CrawlRule.query.all()
    
    manual_rule = None
    if manual_rule_id:
        manual_rule = db.session.get(CrawlRule, int(manual_rule_id))

    for it in items:
        try:
            if not it.url:
                continue
            
            matched_rules = []
            
            if manual_rule:
                # If manual rule is specified, use it first
                matched_rules.append(manual_rule)
            else:
                # Auto match logic
                # 1. Exact match by source name (if rule.match_type == 'source')
                # 2. Domain match by URL (if rule.match_type == 'domain')
                
                # Find source matches
                if it.source:
                    source_matches = [r for r in all_rules if r.match_type == 'source' and r.site == it.source]
                    matched_rules.extend(source_matches)
                
                # Find domain matches
                domain = urllib.parse.urlparse(it.url).netloc
                domain_matches = [r for r in all_rules if r.match_type == 'domain' and r.site and r.site in domain]
                matched_rules.extend(domain_matches)
            
            title = ""
            content = ""
            
            # Try matched rules in order (Cascade)
            for rule in matched_rules:
                try:
                    res = collect_content_by_rule(
                        it.url, 
                        rule.title_xpath, 
                        rule.content_xpath, 
                        rule.headers_json
                    )
                    if res and (res[0] or res[1]):
                        title, content = res
                        if content: # If we got content, stop trying other rules
                            break 
                except Exception as e:
                    print(f"Rule {rule.id} failed for item {it.id}: {e}")
                    continue

            # Fallback if rules failed or no rule found
            if not content:
                # Use generic crawler
                content = deep_collect_content(it.url)
            
            if title:
                it.title = title 
            
            # Save
            if it.deep_content_obj:
                it.deep_content_obj.content = content
            else:
                it.deep_content_obj = DeepCollectionContent(content=content)

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
            # 查重：如果URL或标题已存在，则跳过
            existing = CollectionItem.query.filter(
                (CollectionItem.url == it.get('url')) | 
                (CollectionItem.title == it.get('title'))
            ).first()
            
            if existing:
                continue

            ci = CollectionItem(
                keyword=keyword,
                title=it.get('title'),
                cover=it.get('cover'),
                url=it.get('url'),
                source=it.get('source'),
                deep_collected=bool(it.get('deep_collected'))
            )
            if it.get('deep_content'):
                ci.deep_content_obj = DeepCollectionContent(content=it.get('deep_content'))

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
        # 查重
        existing = CollectionItem.query.filter(
            (CollectionItem.url == item.get('url')) | 
            (CollectionItem.title == item.get('title'))
        ).first()
        
        if existing:
            # 如果已存在，返回成功但不重复添加，或者返回特定状态
            # 这里为了前端兼容，返回已存在的ID
            return jsonify({"id": existing.id, "msg": "Item already exists"})

        ci = CollectionItem(
            keyword=keyword,
            title=item.get('title'),
            cover=item.get('cover'),
            url=item.get('url'),
            source=item.get('source'),
            deep_collected=bool(item.get('deep_collected'))
        )
        if item.get('deep_content'):
            ci.deep_content_obj = DeepCollectionContent(content=item.get('deep_content'))

        db.session.add(ci)
        db.session.commit()
        return jsonify({"id": ci.id})
    except Exception:
        db.session.rollback()
        return jsonify({"error": "save failed"}), 500

# --- AI Engine Routes ---

@bp.route('/ai_engines/list')
@login_required
def ai_engines_list():
    engines = AiEngine.query.order_by(AiEngine.created_at.desc()).all()
    data = []
    for e in engines:
        data.append({
            'id': e.id,
            'provider': e.provider,
            'api_url': e.api_url,
            'api_key': e.api_key,
            'model_name': e.model_name,
            'is_active': e.is_active,
            'created_at': e.created_at.isoformat()
        })
    return jsonify({'items': data})

@bp.route('/ai_engines/create', methods=['POST'])
@login_required
def ai_engines_create():
    payload = request.get_json() or {}
    try:
        engine = AiEngine(
            provider=payload.get('provider'),
            api_url=payload.get('api_url'),
            api_key=payload.get('api_key'),
            model_name=payload.get('model_name'),
            is_active=payload.get('is_active', True)
        )
        db.session.add(engine)
        db.session.commit()
        return jsonify({'id': engine.id})
    except Exception as e:
        db.session.rollback()
        print(f"Create AI Engine error: {e}")
        return jsonify({'error': 'create failed'}), 500

@bp.route('/ai_engines/update', methods=['POST'])
@login_required
def ai_engines_update():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    
    engine = db.session.get(AiEngine, int(id_))
    if not engine:
        return jsonify({'error': 'not found'}), 404
        
    if 'provider' in payload:
        engine.provider = payload.get('provider')
    if 'api_url' in payload:
        engine.api_url = payload.get('api_url')
    if 'api_key' in payload:
        engine.api_key = payload.get('api_key')
    if 'model_name' in payload:
        engine.model_name = payload.get('model_name')
    if 'is_active' in payload:
        engine.is_active = payload.get('is_active')
        
    try:
        db.session.commit()
        return jsonify({'id': engine.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'update failed'}), 500

@bp.route('/ai_engines/delete', methods=['POST'])
@login_required
def ai_engines_delete():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    engine = db.session.get(AiEngine, int(id_))
    if not engine:
        return jsonify({'error': 'not found'}), 404
    
    db.session.delete(engine)
    db.session.commit()
    return jsonify({'deleted': 1})

@bp.route('/ai_engines/test_chat', methods=['POST'])
@login_required
def ai_engines_test_chat():
    payload = request.get_json() or {}
    id_ = payload.get('id')
    message = payload.get('message')
    
    if not id_ or not message:
        return jsonify({'error': 'missing parameters'}), 400
        
    engine = db.session.get(AiEngine, int(id_))
    if not engine:
        return jsonify({'error': 'engine not found'}), 404
        
    if not engine.is_active:
        return jsonify({'error': 'engine is inactive'}), 400
        
    try:
        # Use openai library to call the API
        import openai
        
        client = openai.OpenAI(
            api_key=engine.api_key,
            base_url=engine.api_url
        )
        
        response = client.chat.completions.create(
            model=engine.model_name,
            messages=[
                {"role": "user", "content": message}
            ],
            max_tokens=1024,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content
        return jsonify({'reply': reply})
        
    except ImportError:
        return jsonify({'error': 'openai library not installed'}), 500
    except Exception as e:
        print(f"Chat Test Error: {e}")
        return jsonify({'error': str(e)}), 500
