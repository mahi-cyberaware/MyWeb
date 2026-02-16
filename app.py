import os
import markdown
import cloudinary
import cloudinary.uploader

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from models import db, User, Tool, BlogPost, GalleryFile
from forms import (ToolForm, BlogForm, UploadFileForm,
                   RegistrationForm, LoginForm, ChangePasswordForm, ContactForm,
                   ForgotPasswordForm, ResetPasswordForm)
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension

app = Flask(__name__)

# ================== BASIC CONFIG ==================

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')

# Supabase PostgreSQL
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# Email Config
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

# ================== DATABASE INIT + AUTO ADMIN ==================

@app.before_request
def initialize_database():
    db.create_all()

    # Auto-create admin if not exists
    if not User.query.filter_by(role="admin").first():
        admin = User(
            username="admin",
            email="admin@yourdomain.com",
            password_hash=generate_password_hash("Admin@12345"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")

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
    return render_template('index.html',
                           tool_count=tool_count,
                           file_count=file_count,
                           blog_count=blog_count)

@app.route('/blog')
def blog():
    posts = BlogPost.query.filter_by(published=True)\
        .order_by(BlogPost.date_posted.desc()).all()
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('blog_post.html', post=post)

# ================== AUTH ==================

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = generate_password_hash(form.password.data)
        user = User(username=form.username.data,
                    email=form.email.data,
                    password_hash=hashed,
                    role="user")
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('home'))

# ================== ADMIN BLOG ==================

@app.route('/admin/blog/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_blog():
    form = BlogForm()
    if form.validate_on_submit():

        featured_image = None
        if form.featured_image.data:
            upload_result = cloudinary.uploader.upload(form.featured_image.data)
            featured_image = upload_result["secure_url"]

        post = BlogPost(
            title=form.title.data,
            slug=form.slug.data,
            excerpt=form.excerpt.data,
            content=form.content.data,
            featured_image=featured_image,
            tags=form.tags.data,
            published=form.published.data
        )

        db.session.add(post)
        db.session.commit()
        flash('Blog post added.', 'success')
        return redirect(url_for('home'))

    return render_template('admin/add_blog.html', form=form)

@app.route('/admin/upload-inline-image', methods=['POST'])
@login_required
@admin_required
def upload_inline_image():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file'}), 400

    upload_result = cloudinary.uploader.upload(file)
    return jsonify({'location': upload_result["secure_url"]})

# ================== GALLERY ==================

@app.route('/admin/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_file():
    form = UploadFileForm()
    if form.validate_on_submit():

        upload_result = cloudinary.uploader.upload(form.file.data)

        file_record = GalleryFile(
            filename=form.file.data.filename,
            stored_filename=upload_result["secure_url"],
            file_type=form.file_type.data,
            description=form.description.data,
            size=upload_result.get("bytes", 0)
        )

        db.session.add(file_record)
        db.session.commit()

        flash('File uploaded successfully.', 'success')
        return redirect(url_for('home'))

    return render_template('admin/upload_file.html', form=form)

@app.route('/uploads/<path:url>')
@login_required
def uploaded_file(url):
    return redirect(url)

# ================== RUN ==================

if __name__ == '__main__':
    app.run(debug=True)
