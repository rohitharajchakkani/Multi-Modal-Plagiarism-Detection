"""
Database module for the Plagiarism Detection System.
Handles SQLite connection, initialization, and CRUD operations for PlagiarismAI.
"""
import sqlite3
import json
import os
from config import DATABASE_PATH, SCHEMA_PATH


def get_db():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """Initialize the database by executing the schema file."""
    conn = get_db()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def reset_db():
    """Completely wipe and recreate the database."""
    if os.path.exists(DATABASE_PATH):
        try:
            os.remove(DATABASE_PATH)
        except Exception:
            pass
    init_db()


def save_comparison(comparison_type, input1, input2, similarity_score,
                    method_used, result_category, detailed_results,
                    mode_used='local', file_names=None, user_id=None):
    """
    Save a comparison result to both comparison_history (new) and comparisons (for backward compatibility).
    """
    conn = get_db()
    cursor = conn.cursor()

    # Previews
    input1_preview = input1[:200] if input1 else ''
    input2_preview = input2[:200] if input2 else ''

    # Serialize detailed_results
    detailed_json = json.dumps(detailed_results) if isinstance(detailed_results, dict) else detailed_results

    # Save to old table for safety/compatibility
    try:
        cursor.execute('''
            INSERT INTO comparisons
            (comparison_type, input1_preview, input2_preview, input1_full, input2_full,
             similarity_score, method_used, result_category, detailed_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (comparison_type, input1_preview, input2_preview, input1, input2,
              similarity_score, method_used, result_category, detailed_json))
    except Exception as e:
        print(f"[DB Error] Failed to write to comparisons: {e}")

    # Save to new table (comparison_history)
    cursor.execute('''
        INSERT INTO comparison_history
        (user_id, comparison_type, mode_used, file_names, input1_preview, input2_preview,
         input1_full, input2_full, similarity_score, plagiarism_level, method_used, detailed_results)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, comparison_type, mode_used, file_names, input1_preview, input2_preview,
          input1, input2, similarity_score, result_category, method_used, detailed_json))

    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def save_web_source_result(comparison_id, source_url, source_title, matched_snippet,
                           similarity_score, source_type, reliability_score, confidence_score, plagiarism_level):
    """Save an individual web match source result."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO web_source_results
        (comparison_id, source_url, source_title, matched_snippet, similarity_score,
         source_type, reliability_score, confidence_score, plagiarism_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (comparison_id, source_url, source_title, matched_snippet, similarity_score,
          source_type, reliability_score, confidence_score, plagiarism_level))
    conn.commit()
    conn.close()


def get_comparison(comparison_id):
    """Fetch a single comparison by its ID from the new table, including web sources."""
    conn = get_db()
    row = conn.execute('SELECT * FROM comparison_history WHERE id = ?', (comparison_id,)).fetchone()
    
    if not row:
        # Fallback to old comparisons table
        row = conn.execute('SELECT * FROM comparisons WHERE id = ?', (comparison_id,)).fetchone()
        if not row:
            conn.close()
            return None
        
        result = dict(row)
        result['mode_used'] = 'local'
        result['plagiarism_level'] = result.get('result_category')
        result['file_names'] = None
        if result.get('detailed_results'):
            try:
                result['detailed_results'] = json.loads(result['detailed_results'])
            except Exception:
                result['detailed_results'] = {}
        conn.close()
        return result

    result = dict(row)
    if result.get('detailed_results'):
        try:
            result['detailed_results'] = json.loads(result['detailed_results'])
        except Exception:
            result['detailed_results'] = {}

    # Fetch any associated web sources
    web_rows = conn.execute('SELECT * FROM web_source_results WHERE comparison_id = ?', (comparison_id,)).fetchall()
    result['web_sources'] = [dict(w) for w in web_rows]
    
    conn.close()
    return result


def get_all_comparisons(limit=50, offset=0, filter_type=None):
    """Fetch all comparisons with optional pagination and filtering."""
    conn = get_db()

    if filter_type:
        rows = conn.execute(
            'SELECT * FROM comparison_history WHERE comparison_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (filter_type, limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM comparison_history ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (limit, offset)
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_stats():
    """Get aggregate statistics for PlagiarismAI dashboard."""
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) FROM comparison_history').fetchone()[0]
    
    text_count = conn.execute(
        "SELECT COUNT(*) FROM comparison_history WHERE comparison_type = 'text'"
    ).fetchone()[0]
    
    visual_count = conn.execute(
        "SELECT COUNT(*) FROM comparison_history WHERE comparison_type = 'visual'"
    ).fetchone()[0]
    
    web_text_count = conn.execute(
        "SELECT COUNT(*) FROM comparison_history WHERE comparison_type = 'web_text'"
    ).fetchone()[0]
    
    web_visual_count = conn.execute(
        "SELECT COUNT(*) FROM comparison_history WHERE comparison_type = 'web_visual'"
    ).fetchone()[0]
    
    high_plagiarism = conn.execute(
        "SELECT COUNT(*) FROM comparison_history WHERE plagiarism_level LIKE 'High%'"
    ).fetchone()[0]

    avg_row = conn.execute('SELECT AVG(similarity_score) FROM comparison_history').fetchone()
    avg_score = round(avg_row[0], 1) if avg_row[0] else 0

    recent = conn.execute(
        'SELECT * FROM comparison_history ORDER BY created_at DESC LIMIT 5'
    ).fetchall()

    conn.close()

    return {
        'total': total,
        'text_count': text_count,
        'handwritten_count': visual_count,  # Maintain name for compatibility with standard view
        'visual_count': visual_count,
        'web_text_count': web_text_count,
        'web_visual_count': web_visual_count,
        'high_plagiarism': high_plagiarism,
        'average_score': avg_score,
        'recent': [dict(r) for r in recent]
    }


def get_total_count(filter_type=None):
    """Get total number of comparisons for pagination."""
    conn = get_db()
    if filter_type:
        count = conn.execute(
            'SELECT COUNT(*) FROM comparison_history WHERE comparison_type = ?',
            (filter_type,)
        ).fetchone()[0]
    else:
        count = conn.execute('SELECT COUNT(*) FROM comparison_history').fetchone()[0]
    conn.close()
    return count


def clear_history():
    """Delete all records from comparison_history, web_source_results, and old comparisons."""
    conn = get_db()
    try:
        conn.execute('DELETE FROM web_source_results')
        conn.execute('DELETE FROM comparison_history')
        conn.execute('DELETE FROM comparisons')
        conn.commit()
        conn.execute('VACUUM')
    except Exception as e:
        print(f"[DB Error] Clear history failed: {e}")
    conn.close()


def get_db_size():
    """Get the database file size in MB."""
    if os.path.exists(DATABASE_PATH):
        size_bytes = os.path.getsize(DATABASE_PATH)
        return round(size_bytes / (1024 * 1024), 2)
    return 0


def get_user_by_email(email):
    """Fetch a user by their email address."""
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(username, password, email):
    """Create a new user record."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, password, email))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def add_notification(user_id, message, category='info'):
    """Add a new notification to the database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO notifications (user_id, message, category) VALUES (?, ?, ?)',
        (user_id, message, category)
    )
    conn.commit()
    notif_id = cursor.lastrowid
    conn.close()
    return notif_id


def get_notifications(user_id, limit=5):
    """Retrieve recent notifications for a user."""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_notifications(user_id):
    """Retrieve all notifications for a user."""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notifications_count(user_id):
    """Get count of unread notifications for a user."""
    conn = get_db()
    count = conn.execute(
        'SELECT COUNT(*) FROM notifications WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0',
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def mark_notification_as_read(notification_id):
    """Mark a notification as read."""
    conn = get_db()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
    conn.commit()
    conn.close()


def clear_all_notifications(user_id):
    """Clear all notifications for a user."""
    conn = get_db()
    conn.execute('DELETE FROM notifications WHERE user_id = ? OR user_id IS NULL', (user_id,))
    conn.commit()
    conn.close()


def delete_comparison(comparison_id):
    """Delete a specific comparison record from comparison_history, web_source_results, and comparisons."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM web_source_results WHERE comparison_id = ?', (comparison_id,))
        cursor.execute('DELETE FROM comparison_history WHERE id = ?', (comparison_id,))
        cursor.execute('DELETE FROM comparisons WHERE id = ?', (comparison_id,))
        conn.commit()
        success = True
    except Exception as e:
        print(f"[DB Error] Delete comparison failed: {e}")
        success = False
    conn.close()
    return success
