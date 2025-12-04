from flask import Blueprint, render_template, request, Response, jsonify
from flask_login import login_required, current_user
from tools.baidu_crawler import crawl_baidu_news
from tools.baidu_crawler import deep_collect_content
from app import db
from app.models import CollectionItem
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

@bp.route('/collector/stream')
@login_required
def collector_stream():
    keyword = request.args.get('keyword', '')
    max_count = request.args.get('count', default=20, type=int)

    def sse_event(data):
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        yield sse_event({"type": "start", "keyword": keyword, "total": max_count})
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

@bp.route('/collector/deep', methods=['POST'])
@login_required
def collector_deep():
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({"error": "missing url"}), 400
    content = deep_collect_content(url)
    return jsonify({"deep_content": content, "deep_collected": True})

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
