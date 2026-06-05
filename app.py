"""
Multi-Modal Plagiarism Detection System
Main Flask Application — PlagiarismAI upgraded routes and request handling.
"""
import math
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from config import SECRET_KEY, DEBUG
from database import (
    init_db, save_comparison, get_comparison, get_all_comparisons,
    get_stats, get_total_count, clear_history, get_db_size, save_web_source_result,
    get_user_by_email, create_user, add_notification, get_notifications,
    get_unread_notifications_count, mark_notification_as_read, get_all_notifications,
    clear_all_notifications, delete_comparison
)
from text_extractor import extract_text_from_document
from text_similarity import compare_texts_hybrid
from visual_similarity import compare_visual_documents
from web_search import run_web_source_detection, get_search_credentials
from plagiarism_utils import get_plagiarism_level, is_meaningful_content

# ── Initialize Flask App ──────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize database on startup
init_db()

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.context_processor
def inject_notifications():
    """Inject unread notifications count and recent notifications list into all templates."""
    if session.get('logged_in'):
        user_id = session.get('user_id')
        recent = get_notifications(user_id, limit=5)
        unread = get_unread_notifications_count(user_id)
        return dict(recent_notifications=recent, unread_notifications_count=unread)
    return dict(recent_notifications=[], unread_notifications_count=0)

# Items per page for history pagination
PER_PAGE = 15


# ── Landing Page ──────────────────────────────────────────
@app.route('/')
def landing():
    """Render the landing / hero page."""
    return render_template('landing.html', hide_sidebar=True)


# ── Login Page ────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Render the animated login page. Redirects to select mode on submit."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please enter email and password.', 'error')
            return redirect(url_for('login'))
            
        # Extract a friendly name from email (e.g. jane.doe@example.com -> Jane Doe)
        username = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        
        # Look up or create user in SQLite database
        user = get_user_by_email(email)
        is_new_user = False
        if not user:
            user_id = create_user(username=username, password=password, email=email)
            user = {'id': user_id, 'username': username, 'email': email}
            is_new_user = True
        else:
            user_id = user['id']
            
        session['user_id'] = user_id
        session['user_name'] = user['username']
        session['user_email'] = user['email']
        session['logged_in'] = True
        
        # Seed initial notifications for a new user
        if is_new_user:
            add_notification(user_id, f"Welcome to PlagiarismAI, {username}! Setup completed successfully.", "success")
            add_notification(user_id, "System updated to 2026 edition. Happy detecting!", "info")
            add_notification(user_id, "Need help? Check out our updated About section.", "info")
            
        flash(f'Successfully logged in as {user["username"]}!', 'success')
        return redirect(url_for('select_mode'))
    return render_template('login.html', hide_sidebar=True)


@app.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ── Select Mode Page ──────────────────────────────────────
@app.route('/select')
def select_mode():
    """Render the comparison mode selection page."""
    return render_template('select_mode.html')


# ── Mode 1: Text Document Comparison ──────────────────────
@app.route('/text-document-compare', methods=['GET', 'POST'])
def text_document_compare():
    """
    GET: Show the text document comparison form.
    POST: Process comparing two documents (uploaded files or pasted texts).
    """
    if request.method == 'POST':
        input_mode = request.form.get('input_mode', 'file')
        text1 = ""
        text2 = ""
        file_names = []

        if input_mode == 'paste':
            text1 = request.form.get('text1', '').strip()
            text2 = request.form.get('text2', '').strip()
            file_names = ["Pasted Text 1", "Pasted Text 2"]
        else:
            # File Upload Check
            if 'file1' not in request.files or 'file2' not in request.files:
                flash('Please upload both files.', 'error')
                return redirect(url_for('text_document_compare'))
                
            file1 = request.files['file1']
            file2 = request.files['file2']
            
            if file1.filename == '' or file2.filename == '':
                flash('No selected file.', 'error')
                return redirect(url_for('text_document_compare'))
                
            # Save files temporarily
            f1_sec = secure_filename(file1.filename)
            f2_sec = secure_filename(file2.filename)
            path1 = os.path.join(app.config['UPLOAD_FOLDER'], f1_sec)
            path2 = os.path.join(app.config['UPLOAD_FOLDER'], f2_sec)
            
            file1.save(path1)
            file2.save(path2)
            
            # Extract text
            text1 = extract_text_from_document(path1)
            text2 = extract_text_from_document(path2)
            file_names = [f1_sec, f2_sec]
            
            # Clean up files
            try:
                os.remove(path1)
                os.remove(path2)
            except Exception:
                pass

        # Error check on extracted content
        if text1.startswith("Error:") or text2.startswith("Error:"):
            flash(f"Extraction Error: {text1 if text1.startswith('Error') else text2}", 'error')
            return redirect(url_for('text_document_compare'))

        # Minimum meaningful content validation
        is_val1, err1 = is_meaningful_content(text1, min_tokens=5)
        is_val2, err2 = is_meaningful_content(text2, min_tokens=5)
        if not is_val1 or not is_val2:
            flash("Not enough meaningful content for plagiarism detection.", 'error')
            return redirect(url_for('text_document_compare'))

        # Run text similarity pipeline
        result = compare_texts_hybrid(text1, text2)

        # Save to database
        level_label = get_plagiarism_level(result['overall_score'])['label']
        record_id = save_comparison(
            comparison_type='text',
            input1=text1,
            input2=text2,
            similarity_score=result['overall_score'],
            method_used=result['method'],
            result_category=level_label,
            detailed_results=result,
            mode_used='local',
            file_names=", ".join(file_names),
            user_id=session.get('user_id')
        )

        # Log system notifications
        user_id = session.get('user_id')
        score = round(result['overall_score'], 1)
        file_desc = ", ".join(file_names)
        add_notification(
            user_id=user_id,
            message=f"Text check completed for '{file_desc}' (Score: {score}%).",
            category='info'
        )
        if score >= 40:
            add_notification(
                user_id=user_id,
                message=f"WARNING: Moderate/High similarity of {score}% detected in '{file_desc}'!",
                category='warning'
            )

        return redirect(url_for('result', comparison_id=record_id))

    return render_template('text_document_compare.html')


# ── Mode 2: Visual Document Comparison ────────────────────
@app.route('/visual-document-compare', methods=['GET', 'POST'])
def visual_document_compare():
    """
    GET: Show the visual document comparison form.
    POST: Process files and run OpenCV layout/hashing/color + OCR text matching.
    """
    if request.method == 'POST':
        if 'file1' not in request.files or 'file2' not in request.files:
            flash('Please upload both files.', 'error')
            return redirect(url_for('visual_document_compare'))
            
        file1 = request.files['file1']
        file2 = request.files['file2']
        
        if file1.filename == '' or file2.filename == '':
            flash('No selected files.', 'error')
            return redirect(url_for('visual_document_compare'))
            
        # Save files temporarily
        f1_sec = secure_filename(file1.filename)
        f2_sec = secure_filename(file2.filename)
        path1 = os.path.join(app.config['UPLOAD_FOLDER'], f1_sec)
        path2 = os.path.join(app.config['UPLOAD_FOLDER'], f2_sec)
        
        file1.save(path1)
        file2.save(path2)
        
        # Run computer vision similarity pipeline
        result = compare_visual_documents(path1, path2)
        
        # Clean up files
        try:
            os.remove(path1)
            os.remove(path2)
        except Exception:
            pass

        # Save to database
        level_label = get_plagiarism_level(result['overall_score'])['label']
        record_id = save_comparison(
            comparison_type='visual',
            input1=result.get('ocr_text1', ''),
            input2=result.get('ocr_text2', ''),
            similarity_score=result['overall_score'],
            method_used='OCR + Computer Vision (Layout, Hash, HSV Color)',
            result_category=level_label,
            detailed_results=result,
            mode_used='local',
            file_names=f"{f1_sec}, {f2_sec}",
            user_id=session.get('user_id')
        )

        # Log system notifications
        user_id = session.get('user_id')
        score = round(result['overall_score'], 1)
        file_desc = f"{f1_sec}, {f2_sec}"
        add_notification(
            user_id=user_id,
            message=f"Visual check completed for '{file_desc}' (Score: {score}%).",
            category='info'
        )
        if score >= 40:
            add_notification(
                user_id=user_id,
                message=f"WARNING: Moderate/High similarity of {score}% detected in '{file_desc}'!",
                category='warning'
            )

        return redirect(url_for('result', comparison_id=record_id))

    return render_template('visual_document_compare.html')


# ── Mode 3: AI-Based Web Source Detection Select Page ──────
@app.route('/web-source-detection')
def web_source_detection():
    """Show options for scanning against web sources (Text or Visual)."""
    tavily_key, serpapi_key, provider = get_search_credentials()
    warning = None
    if provider == 'tavily' and not tavily_key:
        warning = "Web search API key is missing. Please add your TAVILY_API_KEY in the .env file."
    elif provider == 'serpapi' and not serpapi_key:
        warning = "Web search API key is missing. Please add your SERPAPI_KEY in the .env file."
        
    return render_template('web_source_detection.html', api_key_warning=warning)


# ── Sub-Mode A: Text Document from Web ────────────────────
@app.route('/web-text-compare', methods=['GET', 'POST'])
def web_text_compare():
    """GET/POST for text web search plagiarism check."""
    tavily_key, serpapi_key, provider = get_search_credentials()
    warning = None
    if provider == 'tavily' and not tavily_key:
        warning = "Web search API key is missing. Please add your TAVILY_API_KEY in the .env file."
    elif provider == 'serpapi' and not serpapi_key:
        warning = "Web search API key is missing. Please add your SERPAPI_KEY in the .env file."

    if request.method == 'POST':
        if warning:
            flash(warning, 'error')
            return redirect(url_for('web_text_compare'))

        # Check if text is pasted or file is uploaded
        text = ""
        file_name = "Pasted Content"
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            file_name = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            file.save(path)
            text = extract_text_from_document(path)
            try:
                os.remove(path)
            except Exception:
                pass
        else:
            text = request.form.get('text', '').strip()

        # Content validation
        is_val, err = is_meaningful_content(text, min_tokens=8)
        if not is_val:
            flash(err, 'error')
            return redirect(url_for('web_text_compare'))

        # Run web detection pipeline
        web_results = run_web_source_detection(text)
        if 'error' in web_results:
            flash(web_results['error'], 'error')
            return redirect(url_for('web_text_compare'))

        matches = web_results.get('matches', [])
        
        # Default similarity parameters if no matches found
        highest_score = 0.0
        plag_level = "No Plagiarism"
        
        if matches:
            highest_score = matches[0]['similarity_score']
            plag_level = matches[0]['plagiarism_level']

        # Save primary record to comparison_history
        detailed = {
            'breakdown': {
                'highest_web_match': highest_score,
                'sources_found': len(matches)
            },
            'confidence_score': matches[0]['confidence_score'] if matches else 100.0,
            'crawler_results': matches
        }
        
        record_id = save_comparison(
            comparison_type='web_text',
            input1=text,
            input2="",
            similarity_score=highest_score,
            method_used=f"Live Web Search ({provider.upper()})",
            result_category=plag_level,
            detailed_results=detailed,
            mode_used='web',
            file_names=file_name,
            user_id=session.get('user_id')
        )

        # Save web source list entries
        for w in matches:
            save_web_source_result(
                comparison_id=record_id,
                source_url=w['url'],
                source_title=w['title'],
                matched_snippet=w['snippet'],
                similarity_score=w['similarity_score'],
                source_type=w['source_type'],
                reliability_score=w['reliability_score'],
                confidence_score=w['confidence_score'],
                plagiarism_level=w['plagiarism_level']
            )

        # Log system notifications
        user_id = session.get('user_id')
        score = round(highest_score, 1)
        add_notification(
            user_id=user_id,
            message=f"Web text check completed for '{file_name}' (Highest match: {score}%).",
            category='info'
        )
        if score >= 40:
            add_notification(
                user_id=user_id,
                message=f"WARNING: Moderate/High web plagiarism of {score}% detected in '{file_name}'!",
                category='warning'
            )

        return redirect(url_for('result', comparison_id=record_id))

    return render_template('web_text_compare.html', api_key_warning=warning)


# ── Sub-Mode B: Visual Document from Web ──────────────────
@app.route('/web-visual-compare', methods=['GET', 'POST'])
def web_visual_compare():
    """GET/POST for OCR visual web scan."""
    tavily_key, serpapi_key, provider = get_search_credentials()
    warning = None
    if provider == 'tavily' and not tavily_key:
        warning = "Web search API key is missing. Please add your TAVILY_API_KEY in the .env file."
    elif provider == 'serpapi' and not serpapi_key:
        warning = "Web search API key is missing. Please add your SERPAPI_KEY in the .env file."

    if request.method == 'POST':
        if warning:
            flash(warning, 'error')
            return redirect(url_for('web_visual_compare'))

        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Please upload a visual file.', 'error')
            return redirect(url_for('web_visual_compare'))

        file = request.files['file']
        file_name = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
        file.save(path)

        # Run OCR extraction
        text = extract_text_from_document(path)
        
        try:
            os.remove(path)
        except Exception:
            pass

        # Check if OCR returned no readable text at all
        if not text or not text.strip() or text.startswith("Error"):
            flash("No readable text detected. Please upload a clearer poster, infographic, handwritten note, or scanned document.", 'error')
            return redirect(url_for('web_visual_compare'))

        # Text Validation
        is_val, err = is_meaningful_content(text, min_tokens=8)
        if not is_val:
            flash("No readable text detected. Please upload a clearer poster, infographic, handwritten note, or scanned document.", 'error')
            return redirect(url_for('web_visual_compare'))

        # Run web detection on OCR text
        web_results = run_web_source_detection(text)
        if 'error' in web_results:
            flash(web_results['error'], 'error')
            return redirect(url_for('web_visual_compare'))

        matches = web_results.get('matches', [])
        highest_score = 0.0
        plag_level = "No Plagiarism"
        
        if matches:
            highest_score = matches[0]['similarity_score']
            plag_level = matches[0]['plagiarism_level']

        detailed = {
            'breakdown': {
                'ocr_text_similarity': highest_score,
                'sources_found': len(matches)
            },
            'confidence_score': matches[0]['confidence_score'] if matches else 100.0,
            'ocr_text1': text,
            'crawler_results': matches
        }

        record_id = save_comparison(
            comparison_type='web_visual',
            input1=text,
            input2="",
            similarity_score=highest_score,
            method_used=f"OCR + Live Web Search ({provider.upper()})",
            result_category=plag_level,
            detailed_results=detailed,
            mode_used='web',
            file_names=file_name,
            user_id=session.get('user_id')
        )

        for w in matches:
            save_web_source_result(
                comparison_id=record_id,
                source_url=w['url'],
                source_title=w['title'],
                matched_snippet=w['snippet'],
                similarity_score=w['similarity_score'],
                source_type=w['source_type'],
                reliability_score=w['reliability_score'],
                confidence_score=w['confidence_score'],
                plagiarism_level=w['plagiarism_level']
            )

        # Log system notifications
        user_id = session.get('user_id')
        score = round(highest_score, 1)
        add_notification(
            user_id=user_id,
            message=f"Web visual check completed for '{file_name}' (Highest match: {score}%).",
            category='info'
        )
        if score >= 40:
            add_notification(
                user_id=user_id,
                message=f"WARNING: Moderate/High web plagiarism of {score}% detected in '{file_name}'!",
                category='warning'
            )

        return redirect(url_for('result', comparison_id=record_id))

    return render_template('web_visual_compare.html', api_key_warning=warning)


# ── Result & Turnitin Dashboard ───────────────────────────
@app.route('/result/<int:comparison_id>')
def result(comparison_id):
    """Display Turnitin/Grammarly-style analysis details."""
    comparison = get_comparison(comparison_id)
    if not comparison:
        flash('Comparison record not found.', 'error')
        return redirect(url_for('dashboard'))
        
    level_meta = get_plagiarism_level(comparison['similarity_score'])
    
    return render_template(
        'result.html',
        comparison=comparison,
        level_meta=level_meta
    )


# ── Batch Text Comparison Matrix ─────────────────────────
@app.route('/batch-text-compare', methods=['POST'])
def batch_text_compare():
    """Accept multiple text files and build NxN similarity matrices."""
    files = request.files.getlist('files[]')
    if not files or len(files) < 2:
        flash('Please upload at least 2 files for batch comparison.', 'error')
        return redirect(url_for('text_document_compare'))

    file_data = []
    for f in files:
        if f.filename:
            f_sec = secure_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], f_sec)
            f.save(path)
            content = extract_text_from_document(path)
            try:
                os.remove(path)
            except Exception:
                pass
            if content and not content.startswith("Error"):
                file_data.append({'name': f_sec, 'content': content})

    if len(file_data) < 2:
        flash('Need at least 2 non-empty files.', 'error')
        return redirect(url_for('text_document_compare'))

    n = len(file_data)
    matrix = [[None] * n for _ in range(n)]
    pairs = []
    
    for i in range(n):
        matrix[i][i] = {'score': 100.0, 'category': 'Self'}
        for j in range(i + 1, n):
            result = compare_texts_hybrid(file_data[i]['content'], file_data[j]['content'])
            level_label = get_plagiarism_level(result['overall_score'])['label']
            matrix[i][j] = {'score': result['overall_score'], 'category': level_label}
            matrix[j][i] = matrix[i][j]
            pairs.append({
                'file1': file_data[i]['name'],
                'file2': file_data[j]['name'],
                'score': result['overall_score'],
                'category': level_label,
            })

    pairs.sort(key=lambda x: x['score'], reverse=True)

    return render_template(
        'batch_result.html',
        mode='text',
        file_names=[d['name'] for d in file_data],
        matrix=matrix,
        pairs=pairs,
        total_files=n
    )


# ── Batch Visual Comparison Matrix ───────────────────────
@app.route('/batch-visual-compare', methods=['POST'])
def batch_visual_compare():
    """Accept multiple visual/image documents and build NxN structural layout matrices."""
    files = request.files.getlist('files[]')
    if not files or len(files) < 2:
        flash('Please upload at least 2 visual documents.', 'error')
        return redirect(url_for('visual_document_compare'))

    file_paths = []
    file_names = []
    
    for f in files:
        if f.filename:
            f_sec = secure_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], f_sec)
            f.save(path)
            file_paths.append(path)
            file_names.append(f_sec)

    n = len(file_paths)
    if n < 2:
        flash('Need at least 2 valid visual files.', 'error')
        return redirect(url_for('visual_document_compare'))

    matrix = [[None] * n for _ in range(n)]
    pairs = []

    try:
        for i in range(n):
            matrix[i][i] = {'score': 100.0, 'category': 'Self'}
            for j in range(i + 1, n):
                result = compare_visual_documents(file_paths[i], file_paths[j])
                level_label = get_plagiarism_level(result['overall_score'])['label']
                matrix[i][j] = {'score': result['overall_score'], 'category': level_label}
                matrix[j][i] = matrix[i][j]
                pairs.append({
                    'file1': file_names[i],
                    'file2': file_names[j],
                    'score': result['overall_score'],
                    'category': level_label,
                })
    finally:
        # Guarantee cleanup
        for path in file_paths:
            try:
                os.remove(path)
            except Exception:
                pass

    pairs.sort(key=lambda x: x['score'], reverse=True)

    return render_template(
        'batch_result.html',
        mode='visual',
        file_names=file_names,
        matrix=matrix,
        pairs=pairs,
        total_files=n
    )


# ── Profile & Settings ────────────────────────────────────
@app.route('/profile')
def profile():
    """Render the user profile page."""
    return render_template('profile.html')


@app.route('/settings')
def settings():
    """Render the user settings page."""
    return render_template('settings.html')


# ── Dashboard ─────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    """Render the dashboard overview with summary metrics."""
    stats = get_stats()
    return render_template('dashboard.html', stats=stats)


# ── History ───────────────────────────────────────────────
@app.route('/history')
def history():
    """Render comparison history list with filter sorting and page tabs."""
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('type', None)

    # Validate filters
    if filter_type and filter_type not in ('text', 'visual', 'web_text', 'web_visual'):
        filter_type = None

    # Calculate pages
    total = get_total_count(filter_type)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PER_PAGE

    comparisons = get_all_comparisons(limit=PER_PAGE, offset=offset, filter_type=filter_type)

    return render_template(
        'history.html',
        comparisons=comparisons,
        page=page,
        total_pages=total_pages,
        filter_type=filter_type
    )


# ── Delete and Re-run Comparison Routes ───────────────────
@app.route('/history/delete/<int:comparison_id>', methods=['GET', 'POST'])
def delete_comparison_route(comparison_id):
    """Delete a comparison record from history."""
    if not session.get('logged_in'):
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
        
    if delete_comparison(comparison_id):
        flash('Comparison record deleted successfully.', 'success')
    else:
        flash('Failed to delete comparison record.', 'error')
        
    return redirect(url_for('history'))


@app.route('/history/rerun/<int:comparison_id>')
def rerun_comparison_route(comparison_id):
    """Re-run a past comparison using saved input text details."""
    if not session.get('logged_in'):
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
        
    comparison = get_comparison(comparison_id)
    if not comparison:
        flash('Comparison record not found.', 'error')
        return redirect(url_for('history'))
        
    comp_type = comparison['comparison_type']
    input1 = comparison.get('input1_full', '')
    input2 = comparison.get('input2_full', '')
    file_names = comparison.get('file_names', 'Re-run Comparison')
    user_id = session.get('user_id')
    
    if comp_type == 'text':
        result = compare_texts_hybrid(input1, input2)
        level_label = get_plagiarism_level(result['overall_score'])['label']
        record_id = save_comparison(
            comparison_type='text',
            input1=input1,
            input2=input2,
            similarity_score=result['overall_score'],
            method_used=result['method'],
            result_category=level_label,
            detailed_results=result,
            mode_used='local',
            file_names=file_names,
            user_id=user_id
        )
        
        # Log notification
        add_notification(
            user_id=user_id,
            message=f"Re-run Text check completed for '{file_names}' (Score: {round(result['overall_score'], 1)}%).",
            category='info'
        )
        flash('Re-run completed successfully.', 'success')
        return redirect(url_for('result', comparison_id=record_id))
        
    elif comp_type in ('web_text', 'web_visual'):
        # Re-run web detection pipeline
        web_results = run_web_source_detection(input1)
        if 'error' in web_results:
            flash(web_results['error'], 'error')
            return redirect(url_for('history'))
            
        matches = web_results.get('matches', [])
        highest_score = matches[0]['similarity_score'] if matches else 0.0
        plag_level = matches[0]['plagiarism_level'] if matches else "No Plagiarism"
        
        detailed = {
            'breakdown': {
                'highest_web_match': highest_score,
                'sources_found': len(matches)
            },
            'confidence_score': matches[0]['confidence_score'] if matches else 100.0,
            'ocr_text1': input1,
            'crawler_results': matches
        }
        
        record_id = save_comparison(
            comparison_type=comp_type,
            input1=input1,
            input2="",
            similarity_score=highest_score,
            method_used=f"Re-run Web Search",
            result_category=plag_level,
            detailed_results=detailed,
            mode_used='web',
            file_names=file_names,
            user_id=user_id
        )
        
        for w in matches:
            save_web_source_result(
                comparison_id=record_id,
                source_url=w['url'],
                source_title=w['title'],
                matched_snippet=w['snippet'],
                similarity_score=w['similarity_score'],
                source_type=w['source_type'],
                reliability_score=w['reliability_score'],
                confidence_score=w['confidence_score'],
                plagiarism_level=w['plagiarism_level']
            )
            
        # Log notification
        add_notification(
            user_id=user_id,
            message=f"Re-run Web scan completed for '{file_names}' (Score: {round(highest_score, 1)}%).",
            category='info'
        )
        flash('Web search re-run completed successfully.', 'success')
        return redirect(url_for('result', comparison_id=record_id))
        
    elif comp_type == 'visual':
        # Fall back to text compare since image is gone
        result = compare_texts_hybrid(input1, input2)
        level_label = get_plagiarism_level(result['overall_score'])['label']
        record_id = save_comparison(
            comparison_type='visual',  # Keep it as visual comparison type
            input1=input1,
            input2=input2,
            similarity_score=result['overall_score'],
            method_used="Text-based re-run (visual source files deleted)",
            result_category=level_label,
            detailed_results=result,
            mode_used='local',
            file_names=file_names,
            user_id=user_id
        )
        
        # Log notification
        add_notification(
            user_id=user_id,
            message=f"Re-run Visual text check completed for '{file_names}' (Score: {round(result['overall_score'], 1)}%).",
            category='info'
        )
        flash('Visual compare re-run (falling back to OCR text analysis) completed successfully.', 'info')
        return redirect(url_for('result', comparison_id=record_id))
        
    else:
        flash('Re-run not supported for this format.', 'error')
        return redirect(url_for('history'))


# ── 404 Error Handler ─────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    """Render a custom error 404 view."""
    return render_template('404.html'), 404


# ── Report Audit Log Page ──────────────────────────────────
@app.route('/report/<int:comparison_id>')
def report(comparison_id):
    """Render full printable audit log report."""
    comparison = get_comparison(comparison_id)
    if not comparison:
        flash('Report records not found.', 'error')
        return redirect(url_for('history'))
        
    level_meta = get_plagiarism_level(comparison['similarity_score'])
    
    return render_template(
        'report.html',
        comparison=comparison,
        level_meta=level_meta
    )


# ── Admin Panel & System ───────────────────────────────────
@app.route('/admin')
def admin():
    """Render system settings and SQLite tables overview."""
    stats = get_stats()
    db_size = get_db_size()
    comparisons = get_all_comparisons(limit=100)
    return render_template(
        'admin.html',
        stats=stats,
        db_size=db_size,
        comparisons=comparisons
    )


@app.route('/admin/clear', methods=['POST'])
def admin_clear():
    """Delete all comparison metrics databases records."""
    clear_history()
    flash('All plagiarism records have been successfully cleared.', 'success')
    return redirect(url_for('admin'))


# ── Notifications Page & Actions ─────────────────────────
@app.route('/notifications')
def notifications_page():
    """Render all notifications for the logged-in user in reverse chronological order."""
    if not session.get('logged_in'):
        flash('Please log in to view notifications.', 'error')
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    all_notifs = get_all_notifications(user_id)
    return render_template('notifications.html', notifications=all_notifs)


@app.route('/notifications/read/<int:notification_id>', methods=['GET', 'POST'])
def read_notification(notification_id):
    """Mark a notification as read."""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    mark_notification_as_read(notification_id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True})
        
    flash('Notification marked as read.', 'success')
    return redirect(request.referrer or url_for('notifications_page'))


@app.route('/notifications/clear', methods=['GET', 'POST'])
def clear_notifications():
    """Clear all notifications for the logged-in user."""
    if not session.get('logged_in'):
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    clear_all_notifications(user_id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True})
        
    flash('All notifications cleared.', 'success')
    return redirect(url_for('notifications_page'))


# ── About ─────────────────────────────────────────────────
@app.route('/about')
def about():
    """Render about platform page."""
    return render_template('about.html')


# ── API endpoints ─────────────────────────────────────────
@app.route('/api/stats')
def api_stats():
    """Return dashboard stats as JSON."""
    stats = get_stats()
    stats['recent'] = [dict(r) for r in stats.get('recent', [])]
    return jsonify(stats)


# ── Run the Application ──────────────────────────────────
if __name__ == '__main__':
    print("\n" + "=" * 55)
    print("  PlagiarismAI System Dashboard Active")
    print("  Running at: http://127.0.0.1:5000")
    print("=" * 55 + "\n")
    app.run(debug=DEBUG, host='127.0.0.1', port=5000)
