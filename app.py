import os
import markdown
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from models import db, User, Tool, BlogPost, News, GalleryFile
from forms import (ToolForm, BlogForm, NewsForm, UploadFileForm,
                   RegistrationForm, LoginForm, ChangePasswordForm,
                   ForgotPasswordForm, ResetPasswordForm, ContactForm)
from datetime import datetime
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from sqlalchemy import or_

app = Flask(__name__)

# ================== CONFIGURATION ==================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'myprogrammwork1@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = 'myprogrammwork1@gmail.com'

mail = Mail(app)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# ================== MARKDOWN FILTER ==================
@app.template_filter('markdown')
def render_markdown(text):
    if not text:
        return ''
    return markdown.markdown(text, extensions=[
        FencedCodeExtension(),
        CodeHiliteExtension(linenums=False),
        'tables',
        'nl2br'
    ])

# ================== DATABASE INIT ==================
_first_request_done = False

@app.before_request
def before_first_request():
    global _first_request_done
    if not _first_request_done:
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                email='admin@localhost',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        _first_request_done = True

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ================== PUBLIC ROUTES ==================
@app.route('/')
def home():
    tool_count = Tool.query.count()
    file_count = GalleryFile.query.count()
    blog_count = BlogPost.query.filter_by(published=True).count()
    news_count = News.query.count()
    latest_posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.date_posted.desc()).limit(4).all()
    latest_news = News.query.order_by(News.date_posted.desc()).limit(4).all()
    contact_form = ContactForm()
    return render_template('index.html',
                           tool_count=tool_count,
                           file_count=file_count,
                           blog_count=blog_count,
                           news_count=news_count,
                           latest_posts=latest_posts,
                           latest_news=latest_news,
                           contact_form=contact_form)

@app.route('/tools')
def tools():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Tool.query

    if search:
        query = query.filter(
            or_(
                Tool.title.ilike(f'%{search}%'),
                Tool.description.ilike(f'%{search}%'),
                Tool.category.ilike(f'%{search}%'),
                Tool.language.ilike(f'%{search}%')
            )
        )
    if category and category != 'all':
        query = query.filter(Tool.category == category)

    pagination = query.order_by(Tool.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
    tools = pagination.items
    categories = db.session.query(Tool.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template('tools.html', tools=tools, pagination=pagination, categories=categories, search=search, current_category=category)

@app.route('/gallery')
def gallery():
    search = request.args.get('search', '')
    file_type = request.args.get('type', 'images')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Determine file_type for query
    if file_type == 'images':
        type_filter = 'image'
    elif file_type == 'videos':
        type_filter = 'video'
    elif file_type == 'code':
        type_filter = 'code'
    else:
        type_filter = 'image'  # default

    query = GalleryFile.query.filter_by(file_type=type_filter)

    if search:
        query = query.filter(
            or_(
                GalleryFile.filename.ilike(f'%{search}%'),
                GalleryFile.description.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(GalleryFile.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    files = pagination.items

    # Get counts for each type (for tabs)
    images_count = GalleryFile.query.filter_by(file_type='image').count()
    videos_count = GalleryFile.query.filter_by(file_type='video').count()
    code_count = GalleryFile.query.filter_by(file_type='code').count()

    return render_template('gallery.html',
                           files=files,
                           pagination=pagination,
                           search=search,
                           file_type=file_type,
                           images_count=images_count,
                           videos_count=videos_count,
                           code_count=code_count)

@app.route('/blog')
def blog():
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 5

    query = BlogPost.query.filter_by(published=True)

    if search:
        query = query.filter(
            or_(
                BlogPost.title.ilike(f'%{search}%'),
                BlogPost.tags.ilike(f'%{search}%'),
                BlogPost.excerpt.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(BlogPost.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items
    return render_template('blog.html', posts=posts, pagination=pagination, search=search)

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('blog_post.html', post=post)

@app.route('/news')
def news_list():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    pagination = News.query.order_by(News.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
    news_items = pagination.items
    trending = News.query.order_by(News.date_posted.desc()).limit(5).all()
    return render_template('news.html', news_items=news_items, pagination=pagination, trending=trending)

@app.route('/news/<slug>')
def news_detail(slug):
    news = News.query.filter_by(slug=slug).first_or_404()
    # Related posts: same category, exclude current, limit 3
    related = News.query.filter(News.category == news.category, News.id != news.id).order_by(News.date_posted.desc()).limit(3).all()
    return render_template('news_detail.html', news=news, related=related)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        msg = Message(subject=f"Contact from {form.name.data}",
                      recipients=['myprogrammwork1@gmail.com'],
                      body=f"Name: {form.name.data}\nEmail: {form.email.data}\n\nMessage:\n{form.message.data}")
        try:
            mail.send(msg)
            flash('Thank you for contacting us. We will get back to you soon!', 'success')
        except Exception as e:
            flash('Error sending message. Please try again later.', 'danger')
        return redirect(url_for('contact'))
    return render_template('contact.html', form=form)

@app.route('/about')
def about():
    return render_template('about.html')

# ================== AUTHENTICATION ==================
# ... (keep all auth routes as before) ...
# ... (include register, login, logout, change_password, forgot_password, reset_password) ...

# ================== ADMIN DASHBOARD ==================
# ... (keep all admin routes) ...

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True)
