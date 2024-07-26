from flask import Flask, request, send_file, jsonify, render_template, session, redirect, url_for, abort, send_from_directory
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from flask_cors import CORS
import sqlite3
import os
import io
import requests
import datetime
from functools import wraps
import sys
sys.path.append('../')
from Utils import db_initializer as db

from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
from pytz import timezone, utc
import pytz

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
app.secret_key = 'Secret'
CORS(app)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'database.db')
message_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'messages.db')


def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization')

        if not api_key:
            abort(401)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT permissions FROM api_keys WHERE api_key = ?', (api_key,))
            key_data = cursor.fetchone()

        if not key_data:
            abort(401)

        return f(*args, **kwargs)

    return decorated_function

    
def calculate_xp_needed(level):
    BASE_XP_NEEDED = 100
    LEVEL_XP_INCREASE = 0.25
    return int(BASE_XP_NEEDED * (level ** (1 + LEVEL_XP_INCREASE)))

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)

@app.route('/artcordlv/api/database', methods=['GET'])
def view_database():
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Fetch users data
            cursor.execute('SELECT * FROM users')
            users_rows = cursor.fetchall()
            
            # Fetch config data
            cursor.execute('SELECT * FROM config')
            config_rows = cursor.fetchall()
            
            # Fetch settings data
            cursor.execute('SELECT * FROM settings')
            setting_rows = cursor.fetchall()
            
            # Fetch quests data
            cursor.execute('SELECT * FROM quests')
            quests_rows = cursor.fetchall()

            # Fetch user quests data
            cursor.execute('SELECT * FROM user_quests')
            user_quests_rows = cursor.fetchall()

        print("Users rows:", users_rows)
        print("Config rows:", config_rows)
        print("Setting rows:", setting_rows)
        print("Quests rows:", quests_rows)
        print("User Quests rows:", user_quests_rows)


        return jsonify({
            'users': users_rows,
            'config': config_rows,
            'settings': setting_rows,
            'quests': quests_rows,
            'user_quests': user_quests_rows

        })

    except sqlite3.Error as e:
        print(f"Database error fetching contents: {e}")
        return jsonify({'error': 'Database Error'}), 500
    except Exception as e:
        print(f"Unexpected error fetching contents: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500
    
def get_db():
    mdb = sqlite3.connect(message_db_path)
    print(message_db_path)
    mdb.row_factory = sqlite3.Row
    return mdb


@app.route('/artcordlv/api/message_database_info', methods=['GET'])
def database_info():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM messages;")
    rows = c.fetchall()
    
    c.execute("PRAGMA table_info(messages);")
    columns = [column[1] for column in c.fetchall()]
    data = [dict(zip(columns, row)) for row in rows]
    conn.close()
    
    return jsonify({'messages': data})

@app.route('/artcordlv/api/message_data', methods=['GET'])
def message_data():
    conn = get_db()
    c = conn.cursor()

    time_frame = request.args.get('timeFrame')
    date_param = request.args.get('date')
    hour_param = request.args.get('hour')
    from_hour = int(request.args.get('from', 0))
    to_hour = int(request.args.get('to', 23))
    duration = int(request.args.get('duration', 1))
    include_users = request.args.get('users', 'false').lower() == 'true'
    timezone_arg = request.args.get('timezone', 'America/Los_Angeles')

    try:
        tz_user = timezone(timezone_arg)
    except pytz.UnknownTimeZoneError:
        return jsonify({'error': f'Unknown timezone: {timezone_arg}'}), 400

    today = datetime.now(utc)

    try:
        if time_frame == 'year':
            year = int(date_param.split('-')[0])
            start_date = datetime(year, 1, 1).replace(tzinfo=tz_user).astimezone(utc)
            end_date = start_date + timedelta(days=365 * duration)
        elif time_frame == 'month':
            year, month = map(int, date_param.split('-'))
            start_date = datetime(year, month, 1).replace(tzinfo=tz_user).astimezone(utc)
            end_date = start_date + timedelta(days=32 * duration)
        elif time_frame == 'week':
            iso_year, iso_week, _ = datetime.strptime(date_param, '%Y-%m-%d').isocalendar()
            start_date = datetime.strptime(f'{iso_year}-W{iso_week}-1', '%G-W%V-%u').replace(tzinfo=tz_user).astimezone(utc)
            end_date = start_date + timedelta(days=7 * duration)
        elif time_frame == 'day':
            if hour_param:
                hour = int(hour_param)
                year, month, day = map(int, date_param.split('-'))
                start_date = datetime(year, month, day, hour).replace(tzinfo=tz_user).astimezone(utc)
                end_date = start_date + timedelta(hours=duration)
            else:
                year, month, day = map(int, date_param.split('-'))
                start_date = datetime(year, month, day).replace(tzinfo=tz_user).astimezone(utc)
                end_date = start_date + timedelta(days=duration)
        elif time_frame == 'hour':
            if from_hour < 0 or from_hour > 23 or to_hour < 0 or to_hour > 23 or from_hour > to_hour:
                return jsonify({'error': 'Invalid hour range'}), 400

            year, month, day = map(int, date_param.split('-'))
            start_date = datetime(year, month, day, from_hour).replace(tzinfo=tz_user).astimezone(utc)
            end_date = datetime(year, month, day, to_hour, 59).replace(tzinfo=tz_user).astimezone(utc)
        else:
            return jsonify({'error': 'Invalid time frame format'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid time frame format'}), 400

    if include_users:
        c.execute('SELECT user_id, timestamp FROM messages WHERE timestamp BETWEEN ? AND ?', (start_date.isoformat(), end_date.isoformat()))
        rows = c.fetchall()
        user_messages = {}
        for row in rows:
            user_id = row['user_id']
            timestamp = datetime.fromisoformat(row['timestamp']).replace(tzinfo=utc)
            timestamp_localized = timestamp.astimezone(tz_user).isoformat()
            if user_id not in user_messages:
                user_messages[user_id] = {'user_id': user_id, 'timestamps': []}
            user_messages[user_id]['timestamps'].append(timestamp_localized)

        conn.close()
        return jsonify(list(user_messages.values()))
    else:
        c.execute('SELECT timestamp FROM messages WHERE timestamp BETWEEN ? AND ?', (start_date.isoformat(), end_date.isoformat()))
        rows = c.fetchall()
        message_data = [{'timestamp': datetime.fromisoformat(row['timestamp']).replace(tzinfo=utc).astimezone(tz_user).isoformat()} for row in rows]
        conn.close()

        date_counts = {}

        for msg in message_data:
            timestamp = datetime.fromisoformat(msg['timestamp'])
            if start_date <= timestamp <= end_date:
                if time_frame == 'year':
                    key = f"{timestamp.year}-{timestamp.month}-{timestamp.day}"
                elif time_frame == 'month':
                    key = f"{timestamp.month}-{timestamp.day}"
                elif time_frame == 'week':
                    iso_year, iso_week, _ = timestamp.isocalendar()
                    key = f"Week {iso_week} - {timestamp.month}-{timestamp.day}"
                elif time_frame == 'day':
                    key = f"{timestamp.hour:02}:00 - {timestamp.hour:02}:59"
                elif time_frame == 'hour':
                    key = f"{timestamp.hour:02}:{timestamp.minute:02}"

                if key in date_counts:
                    date_counts[key] += 1
                else:
                    date_counts[key] = 1

        return jsonify(date_counts)

def get_user_data_from_db(user_id=None, username=None):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        elif username:
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        if user_data:
            user_data = {
                'id': user_data[0],
                'username': user_data[1],
                'nickname': user_data[2],
                'xp': user_data[3],
                'level': user_data[4],
                'avatar_url': user_data[5],
                'xp_needed': user_data[6],
                'total_xp': user_data[7],
                'card_bg_color': user_data[8],
                'card_bg_img_url': user_data[9],
                'card_text_color': user_data[10],
                'card_progress_bar_color': user_data[11]
            }
        return user_data


@app.route('/artcordlv/users', methods=['GET'])
def get_user():
    user_id = request.args.get('user_id', type=int)
    username = request.args.get('username', type=str)

    if user_id is None and username is None:
        return jsonify({'error': 'Either user_id or username must be provided'}), 400

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute('SELECT id, username, nickname, xp, level, avatar_url, xp_needed, total_xp, card_bg_color, card_bg_img_url, card_text_color, card_progress_bar_color FROM users WHERE id = ?', (user_id,))
        elif username is not None:
            cursor.execute('SELECT id, username, nickname, xp, level, avatar_url, xp_needed, total_xp, card_bg_color, card_bg_img_url, card_text_color, card_progress_bar_color FROM users WHERE username = ?', (username,))

        user = cursor.fetchone()

    if user:
        return jsonify({
            'id': user[0],
            'username': user[1],
            'nickname': user[2],
            'xp': user[3],
            'level': user[4],
            'avatar_url': user[5],
            'xp_needed': user[6],
            'total_xp': user[7],
            'card_bg_color': user[8],
            'card_bg_img_url': user[9],
            'card_text_color': user[10],
            'card_progress_bar_color': user[11],
        })
    else:
        return jsonify({'error': 'User not found'}), 404
    
@app.route('/artcordlv/api/leaderboard', methods=['GET'])
def leaderboard():
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, xp, level, xp_needed, total_xp, avatar_url 
                FROM users 
                ORDER BY total_xp DESC 
                LIMIT 10
            ''')
            leaderboard = cursor.fetchall()

        leaderboard_data = [{
            'rank': idx + 1,
            'id': row[0],
            'username': row[1],
            'xp': int(row[2]),
            'level': row[3],
            'xp_needed': row[4],
            'total_xp': row[5],
            'avatar_url': row[6]
        } for idx, row in enumerate(leaderboard)]

        return jsonify(leaderboard_data)

    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

def draw_slanted_polygon(image, color, top_left, top_right, bottom_right, bottom_left):
    draw = ImageDraw.Draw(image)
    draw.polygon([top_left, top_right, bottom_right, bottom_left], fill=color)

# Function to generate the card
def generate_card(user_data, rank=None):
    width, height = 1200, 300
    
    # Load background image from URL and resize
    response = requests.get(user_data['card_bg_img_url'])
    bg_image = Image.open(io.BytesIO(response.content))
    bg_image = bg_image.resize((width, height), Image.LANCZOS)  # Resize to match card dimensions
    
    # Convert background image to RGBA
    bg_image = bg_image.convert('RGBA')

    # Create a blurred version of the background image
    blurred_bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=4))

    # Adjust alpha to give it a dark tint
    alpha_factor = 0.0  # Adjust transparency level here (0.0 to 1.0)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, int(255 * alpha_factor)))
    bg_image = Image.alpha_composite(blurred_bg_image, overlay)

    # Create a new image for the card
    card = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    card.paste(bg_image)

    draw = ImageDraw.Draw(card)

    username_font_size = 80
    if 'nickname' in user_data and user_data['nickname']:
        username_text = user_data['nickname']
    else:
        username_text = user_data['username']

    # Adjust font size based on username length
    if len(username_text) > 7:
        username_font_size -= (len(username_text) - 7) * 2  # Decrease font size by 2 for each character over 7

    if len(username_text) > 24:
        username_font_size = 80
        username_text = user_data['username']

    username_font = ImageFont.truetype("arial.ttf", username_font_size)
    details_font = ImageFont.truetype("arial.ttf", 43)

    # Draw Profile Picture
    response = requests.get(user_data['avatar_url'])
    pfp = Image.open(io.BytesIO(response.content)).resize((300, 300), Image.LANCZOS)
    pfp = pfp.convert("RGBA")
    
    # Create an elliptical mask with anti-aliasing
    mask = Image.new('L', (300, 300), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 300, 300), fill=255, outline=0)
    mask = mask.filter(ImageFilter.SMOOTH)
    
    # Apply the mask to the profile picture
    pfp.putalpha(mask)
    pfp = ImageOps.fit(pfp, (200, 200), method=0, bleed=0.0, centering=(0.5, 0.5))
    
    # Calculate the coordinates for pasting the profile picture
    pfp_x = 30
    pfp_y = 20
    pfp_box = (pfp_x, pfp_y, pfp_x + pfp.width, pfp_y + pfp.height)
    
    # Overlay another image on top of the background
    overlay_img_url = "http://127.0.0.1:5000/images/overlay.png"
    response_overlay = requests.get(overlay_img_url)
    overlay_img = Image.open(io.BytesIO(response_overlay.content))
    overlay_img = overlay_img.resize((width, height), Image.LANCZOS)
    
    # Convert overlay image to RGBA
    overlay_img = overlay_img.convert('RGBA')

    # Convert card_bg_color from database (without #) to Pillow compatible format
    card_bg_color = user_data['card_bg_color']
    if not card_bg_color.startswith('#'):
        card_bg_color = '#' + card_bg_color

    # Create a color overlay
    color_overlay = Image.new('RGBA', (width, height), card_bg_color)

    # Blend the overlay image and color overlay
    combined_overlay = Image.blend(overlay_img, color_overlay, alpha=0.2)

    # Paste the combined overlay image onto the card
    card.paste(combined_overlay, (0, 0), mask=combined_overlay.split()[3])

    # Paste the profile picture onto the card
    card.paste(pfp, pfp_box, mask=pfp.split()[3])

    username_bbox = draw.textbbox((0, 0), username_text, font=username_font)
    username_width = username_bbox[2] - username_bbox[0]
    username_height = username_bbox[3] - username_bbox[1]
    username_x = (width - username_width) // 2
    draw.text((username_x, 40), username_text, font=username_font, fill=user_data['card_text_color'])

    # Draw Level, XP, and Rank in a straight line below username
    if rank is not None:
        level_xp_rank_text = f"Rank: {rank}  Level: {user_data['level']}  XP: {user_data['xp'] / 1000:.1f}K / {user_data['xp_needed'] / 1000:.1f}K"
    else:
        level_xp_rank_text = f"Level: {user_data['level']}  XP: {user_data['xp'] / 1000:.1f}K / {user_data['xp_needed'] / 1000:.1f}K"
    
    level_xp_rank_bbox = draw.textbbox((0, 0), level_xp_rank_text, font=details_font)
    level_xp_rank_width = level_xp_rank_bbox[2] - level_xp_rank_bbox[0]
    level_xp_rank_height = level_xp_rank_bbox[3] - level_xp_rank_bbox[1]
    level_xp_rank_x = (width - level_xp_rank_width) // 2
    draw.text((level_xp_rank_x, 150), level_xp_rank_text, font=details_font, fill=user_data['card_text_color'])

    # Draw Progress Bar only if user has XP
    if user_data['xp'] >= 0:
        progress_bar_x = 30
        progress_bar_y = 240
        progress_bar_width = 950
        progress_bar_height = 40
        xp_progress = user_data['xp'] % user_data['xp_needed']
        progress = int((xp_progress / user_data['xp_needed']) * progress_bar_width)
        
        draw.rounded_rectangle([progress_bar_x, progress_bar_y, progress_bar_x + progress_bar_width, progress_bar_y + progress_bar_height],
                               radius=15, fill='#727D84', outline=None)
        if user_data['xp'] > 0:
            draw.rounded_rectangle([progress_bar_x, progress_bar_y, progress_bar_x + progress, progress_bar_y + progress_bar_height],
                                radius=15, fill=user_data['card_progress_bar_color'], outline=None)

    return card.convert('RGB')

# Function to generate leaderboard image
def generate_leaderboard(entries):
    # Constants for the leaderboard card
    width, height = 600, 685
    num_entries = 10
    gap_height = 5  
    pfp_size = 45
    default_text_color = (255, 255, 255)
    bg_color = "#1E1E1E"  
    row_color = "#434343"  
    ranking_colors = ['#ffd700', '#c0c0c0', '#cd7f32']  # Gold, Silver, Bronze

    # Create a new image for the leaderboard with rounded corners and transparent background
    leaderboard_card = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(leaderboard_card)

    # Draw rounded rectangle for the background of the entire card
    draw_rounded_rectangle(draw, (0, 0, width, height), bg_color, radius=15)

    # Load fonts
    username_font_size = 24
    username_font = ImageFont.truetype("arial.ttf", username_font_size)
    details_font_size = 20
    details_font = ImageFont.truetype("arial.ttf", details_font_size)

    # Calculate entry height slightly smaller than original
    entry_height = (height - (num_entries - 1) * gap_height) // num_entries - 5 

    # Centering variables
    total_rows_height = num_entries * entry_height + (num_entries - 1) * gap_height
    top_margin = (height - total_rows_height) // 2

    # Width adjustment
    row_width = width - 40

    # Fetch entries from database
    fetched_entries = []
    for entry in entries:
        user_data = get_user_data_from_db(username=entry['username'])
        if user_data:
            entry.update(user_data)
            fetched_entries.append(entry)

    # Draw each row
    for rank in range(1, num_entries + 1):
        found_entry = False

        for entry in fetched_entries:
            if entry['rank'] == rank:
                found_entry = True
                # Fetch user data for each entry
                if entry['nickname']:
                    display_name = entry['nickname']
                else:
                    display_name = entry['username']

                level = entry['level']
                pfp_url = entry['avatar_url']
                card_text_color = entry.get('card_text_color')

                # Determine font color based on rank and card_text_color
                if rank <= 3 and card_text_color:
                    try:
                        text_color = tuple(int(card_text_color[i:i+2], 16) for i in (1, 3, 5))
                    except ValueError:
                        text_color = default_text_color
                else:
                    text_color = default_text_color

                # Calculate coordinates for each entry
                entry_y = top_margin + (rank - 1) * (entry_height + gap_height)

                # Draw background color for the row with rounded corners
                draw_rounded_rectangle(draw, (20, entry_y, width - 20, entry_y + entry_height), row_color, 15)

                # Draw a thicker and rounded border for 1st, 2nd, and 3rd place entries
                if rank <= 3:
                    border_color = ranking_colors[rank - 1]
                    draw_rounded_rectangle(draw, (20, entry_y, width - 20, entry_y + entry_height), None, 15, outline=border_color, width=5)

                # Draw profile picture
                response = requests.get(pfp_url)
                pfp = Image.open(io.BytesIO(response.content)).resize((pfp_size, pfp_size), Image.LANCZOS).convert("RGBA")
                leaderboard_card.paste(pfp, (40, entry_y + (entry_height - pfp_size) // 2), mask=pfp.split()[3])

                # Draw rank
                draw.text((140, entry_y + (entry_height - username_font_size) // 2), f"#{rank}", font=details_font, fill=text_color)

                # Draw username/nickname
                draw.text((220, entry_y + (entry_height - username_font_size) // 2), display_name, font=username_font, fill=text_color)

                # Draw level all the way to the right
                level_text = f"LV: {level}"
                level_text_size = draw.textbbox((0, 0), level_text, font=details_font)
                draw.text((width - level_text_size[2] - 40, entry_y + (entry_height - details_font_size) // 2), level_text, font=details_font, fill=text_color)
                break

        if not found_entry:
            # If no entry is found for the current rank, display a message
            entry_y = top_margin + (rank - 1) * (entry_height + gap_height)
            draw_rounded_rectangle(draw, (20, entry_y, width - 20, entry_y + entry_height), row_color, 15)
            draw.text((140, entry_y + (entry_height - username_font_size) // 2), f"No entry for Rank #{rank}", font=details_font, fill=text_color)

    return leaderboard_card.convert('RGB')


def draw_rounded_rectangle(draw, xy, color, radius, outline=None, width=0):
    x0, y0, x1, y1 = xy

    if color:
        # Draw the main rectangle with rounded corners
        draw.rectangle([(x0 + radius, y0), (x1 - radius, y1)], fill=color)  # Top edge
        draw.rectangle([(x0, y0 + radius), (x1, y1 - radius)], fill=color)  # Side edges

        # Draw the smoother rounded corners using pie slices
        draw.pieslice([(x0, y0), (x0 + radius * 2, y0 + radius * 2)], 180, 270, fill=color)  # Top-left corner
        draw.pieslice([(x1 - radius * 2, y0), (x1, y0 + radius * 2)], 270, 360, fill=color)  # Top-right corner
        draw.pieslice([(x0, y1 - radius * 2), (x0 + radius * 2, y1)], 90, 180, fill=color)  # Bottom-left corner
        draw.pieslice([(x1 - radius * 2, y1 - radius * 2), (x1, y1)], 0, 90, fill=color)  # Bottom-right corner


@app.route('/card')
def card():
    user_id = request.args.get('user_id', type=int)
    username = request.args.get('username', type=str)

    if user_id is None and username is None:
        return jsonify({'error': 'Either user_id or username must be provided'}), 400

    user_data = get_user_data_from_db(user_id=user_id, username=username)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    leaderboard_api_url = f'http://127.0.0.1:5000/artcordlvapi/leaderboard'
    response = requests.get(leaderboard_api_url)
    if response.status_code == 200:
        leaderboard_data = response.json()
        for user in leaderboard_data:
            if user['id'] == user_data['id']:
                user_rank = user['rank']
                break
        else:
            user_rank = None
    else:
        user_rank = None

    card_image = generate_card(user_data, rank=user_rank)
    img_io = io.BytesIO()
    card_image.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

@app.route('/img/leaderboard')
def leaderboard_img():
    # Fetch leaderboard data from an API endpoint
    leaderboard_api_url = 'http://127.0.0.1:5000/artcordlv/api/leaderboard'
    response = requests.get(leaderboard_api_url)
    
    if response.status_code == 200:
        leaderboard_data = response.json()
    else:
        return jsonify({'error': 'Failed to fetch leaderboard data'}), 500
    
    # Prepare entries for the leaderboard image generator
    entries = []
    for user in leaderboard_data:
        entry = {
            'rank': user['rank'],
            'username': user['username'],
            'level': user['level'],
            'avatar_url': user['avatar_url']
        }
        entries.append(entry)
    
    # Generate the leaderboard image using the function we defined earlier
    leaderboard_image = generate_leaderboard(entries)
    
    # Convert image to bytes to send as response
    img_io = io.BytesIO()
    leaderboard_image.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

def run_app():
    db.init_db()
    app.run(port=5000)

if __name__ == '__main__':
    run_app()