import os
import re
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
from sqlalchemy import or_, inspect, text
from slugify import slugify

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

# ================== ONE-TIME MIGRATION ROUTE (remove after use) ==================
@app.route('/fix-news-schema')
def fix_news_schema():
    """ONE-TIME route to add slug column to news table and populate slugs."""
    try:
        inspector = inspect(db.engine)
        if 'news' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('news')]
            if 'slug' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE news ADD COLUMN slug VARCHAR(200) UNIQUE'))
                    conn.commit()
                # Generate slugs for existing news
                news_items = News.query.all()
                for item in news_items:
                    if not item.slug:
                        base_slug = slugify(item.title)
                        slug = base_slug
                        counter = 1
                        while News.query.filter_by(slug=slug).first():
                            slug = f"{base_slug}-{counter}"
                            counter += 1
                        item.slug = slug
                db.session.commit()
                return "✅ Added slug column and generated slugs for existing news. You can now remove this route."
            else:
                return "Column 'slug' already exists."
        else:
            return "Table 'news' not found."
    except Exception as e:
        return f"Error: {e}"

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

    if file_type == 'images':
        type_filter = 'image'
    elif file_type == 'videos':
        type_filter = 'video'
    elif file_type == 'code':
        type_filter = 'code'
    else:
        type_filter = 'image'

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
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed, role='user')
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Logged in successfully.', 'success')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.old_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('Your password has been updated.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Old password is incorrect.', 'danger')
    return render_template('change_password.html', form=form)

# ================== PASSWORD RESET ==================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request',
                          recipients=[user.email],
                          body=f'Click the link to reset your password: {reset_url}\n\nIf you did not request this, ignore this email.')
            try:
                mail.send(msg)
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                flash('Error sending email. Please try again later.', 'danger')
        else:
            flash('If that email is registered, a reset link will be sent.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(form.password.data)
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('forgot_password'))
    return render_template('reset_password.html', form=form, token=token)

# ================== ADMIN DASHBOARD ==================
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    tools = Tool.query.order_by(Tool.date_posted.desc()).limit(5).all()
    posts = BlogPost.query.order_by(BlogPost.date_posted.desc()).limit(5).all()
    news = News.query.order_by(News.date_posted.desc()).limit(5).all()
    files = GalleryFile.query.order_by(GalleryFile.upload_date.desc()).limit(5).all()
    return render_template('admin/dashboard.html', tools=tools, posts=posts, news=news, files=files)

# ================== TOOL ADMIN ==================
@app.route('/admin/tool/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_tool():
    form = ToolForm()
    if form.validate_on_submit():
        image_url = None
        if form.image.data:
            upload_result = cloudinary.uploader.upload(form.image.data)
            image_url = upload_result['secure_url']
        category = form.category.data
        if category == 'Other' and request.form.get('custom_category'):
            category = request.form.get('custom_category')
        tool = Tool(
            title=form.title.data,
            description=form.description.data,
            category=category,
            language=form.language.data,
            code=form.code.data,
            github_url=form.github_url.data,
            image_url=image_url
        )
        db.session.add(tool)
        db.session.commit()
        flash('Tool added successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_tool.html', form=form)

@app.route('/admin/tool/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_tool(id):
    tool = Tool.query.get_or_404(id)
    form = ToolForm(obj=tool)
    if form.validate_on_submit():
        if form.image.data:
            upload_result = cloudinary.uploader.upload(form.image.data)
            tool.image_url = upload_result['secure_url']
        category = form.category.data
        if category == 'Other' and request.form.get('custom_category'):
            category = request.form.get('custom_category')
        tool.category = category
        form.populate_obj(tool)
        db.session.commit()
        flash('Tool updated', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/edit_tool.html', form=form, tool=tool)

@app.route('/admin/tool/delete/<int:id>')
@login_required
@admin_required
def delete_tool(id):
    tool = Tool.query.get_or_404(id)
    db.session.delete(tool)
    db.session.commit()
    flash('Tool deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# ================== BLOG ADMIN ==================
@app.route('/admin/blog/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_blog():
    form = BlogForm()
    if form.validate_on_submit():
        featured_image = None
        if form.featured_image.data:
            upload_result = cloudinary.uploader.upload(form.featured_image.data)
            featured_image = upload_result['secure_url']
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
        flash('Blog post added', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_blog.html', form=form)

@app.route('/admin/blog/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_blog(id):
    post = BlogPost.query.get_or_404(id)
    form = BlogForm(obj=post)
    if form.validate_on_submit():
        if form.featured_image.data:
            upload_result = cloudinary.uploader.upload(form.featured_image.data)
            post.featured_image = upload_result['secure_url']
        form.populate_obj(post)
        db.session.commit()
        flash('Blog post updated', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/edit_blog.html', form=form, post=post)

@app.route('/admin/blog/delete/<int:id>')
@login_required
@admin_required
def delete_blog(id):
    post = BlogPost.query.get_or_404(id)
    db.session.delete(post)
    db.session.commit()
    flash('Blog post deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# ================== NEWS ADMIN ==================
@app.route('/admin/news/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        image_url = None
        if form.image.data:
            upload_result = cloudinary.uploader.upload(form.image.data)
            image_url = upload_result['secure_url']
        # Generate slug from title
        base_slug = slugify(form.title.data)
        slug = base_slug
        counter = 1
        while News.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        news = News(
            title=form.title.data,
            slug=slug,
            excerpt=form.excerpt.data,
            content=form.content.data,
            image_url=image_url,
            category='General'  # default category, can be extended
        )
        db.session.add(news)
        db.session.commit()
        flash('News added successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_news.html', form=form)

@app.route('/admin/news/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_news(id):
    news = News.query.get_or_404(id)
    form = NewsForm(obj=news)
    if form.validate_on_submit():
        if form.image.data:
            upload_result = cloudinary.uploader.upload(form.image.data)
            news.image_url = upload_result['secure_url']
        # Update slug if title changed
        if news.title != form.title.data:
            base_slug = slugify(form.title.data)
            slug = base_slug
            counter = 1
            while News.query.filter(News.slug == slug, News.id != id).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            news.slug = slug
        form.populate_obj(news)
        db.session.commit()
        flash('News updated', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/edit_news.html', form=form, news=news)

@app.route('/admin/news/delete/<int:id>')
@login_required
@admin_required
def delete_news(id):
    news = News.query.get_or_404(id)
    db.session.delete(news)
    db.session.commit()
    flash('News deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# ================== GALLERY ADMIN ==================
@app.route('/admin/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_file():
    form = UploadFileForm()
    if form.validate_on_submit():
        upload_result = cloudinary.uploader.upload(form.file.data)
        file_record = GalleryFile(
            filename=form.file.data.filename,
            stored_filename=upload_result['secure_url'],
            file_type=form.file_type.data,
            description=form.description.data,
            size=upload_result.get('bytes', 0)
        )
        db.session.add(file_record)
        db.session.commit()
        return jsonify({'message': 'File uploaded successfully'}), 200
    return render_template('admin/upload_file.html', form=form)

@app.route('/admin/file/delete/<int:id>')
@login_required
@admin_required
def delete_file(id):
    file_record = GalleryFile.query.get_or_404(id)
    db.session.delete(file_record)
    db.session.commit()
    flash('File deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# ================== INLINE IMAGE UPLOAD ==================
@app.route('/admin/upload-inline-image', methods=['POST'])
@login_required
@admin_required
def upload_inline_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        return jsonify({'error': 'File type not allowed'}), 400

    upload_result = cloudinary.uploader.upload(file)
    image_url = upload_result['secure_url']
    return jsonify({'location': image_url})

if __name__ == '__main__':
    app.run(debug=True)
