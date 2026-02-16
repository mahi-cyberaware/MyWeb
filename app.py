import os
import uuid
import markdown
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from models import db, User, Tool, BlogPost, GalleryFile, BlogImage
from forms import (ToolForm, BlogForm, UploadFileForm, 
                   RegistrationForm, LoginForm, ChangePasswordForm, ContactForm,
                   ForgotPasswordForm, ResetPasswordForm)
from datetime import datetime
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')

# Database configuration – use PostgreSQL if DATABASE_URL is set, else SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Separate folder for blog images
BLOG_IMAGES_FOLDER = os.path.join('uploads', 'blog_images')
os.makedirs(BLOG_IMAGES_FOLDER, exist_ok=True)

# Email config
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

# Serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Markdown filter for templates
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

# Initialize database and admin (runs only once)
_first_request_done = False

@app.before_request
def before_first_request():
    global _first_request_done
    if not _first_request_done:
        db.create_all()
        # Check if admin exists, if not create with default password
        if not User.query.filter_by(username='admin').first():
            hashed = generate_password_hash('admin')  # default, will be changed later
            admin = User(username='admin', 
                         email='admin@localhost', 
                         password_hash=hashed,
                         role='admin')
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
            flash('You need admin privileges to access this page.')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- TEMPORARY ROUTE TO SET ADMIN PASSWORD (DELETE AFTER USE) ----------
@app.route('/force-change-password')
def force_change_password():
    """ONE-TIME route to set admin password - DELETE AFTER USE!"""
    user = User.query.filter_by(username='admin').first()
    if user:
        new_password = 'PasswordMysite@8080#'
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        return f"✅ Admin password successfully changed to: <strong>{new_password}</strong><br><br>⚠️ **DELETE THIS ROUTE NOW!**"
    return "❌ Admin user not found."
# ---------- END TEMPORARY ROUTE ----------

# ---------- Public Routes ----------
@app.route('/')
def home():
    tool_count = Tool.query.count()
    file_count = GalleryFile.query.count()
    blog_count = BlogPost.query.filter_by(published=True).count()
    return render_template('index.html', tool_count=tool_count, file_count=file_count, blog_count=blog_count)

@app.route('/tools')
def tools():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = Tool.query.order_by(Tool.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
    tools = pagination.items
    categories = db.session.query(Tool.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template('tools.html', tools=tools, pagination=pagination, categories=categories)

@app.route('/gallery')
def gallery():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    images_pagination = GalleryFile.query.filter_by(file_type='image').order_by(GalleryFile.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    videos_pagination = GalleryFile.query.filter_by(file_type='video').order_by(GalleryFile.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    code_pagination = GalleryFile.query.filter_by(file_type='code').order_by(GalleryFile.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('gallery.html',
                           images=images_pagination.items,
                           videos=videos_pagination.items,
                           code_files=code_pagination.items,
                           images_pagination=images_pagination,
                           videos_pagination=videos_pagination,
                           code_pagination=code_pagination)

@app.route('/blog')
def blog():
    page = request.args.get('page', 1, type=int)
    per_page = 5
    pagination = BlogPost.query.filter_by(published=True).order_by(BlogPost.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items
    return render_template('blog.html', posts=posts, pagination=pagination)

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('blog_post.html', post=post)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        msg = Message(subject=form.subject.data,
                      recipients=['myprogrammwork1@gmail.com'],
                      body=f"From: {form.name.data} <{form.email.data}>\n\n{form.message.data}")
        try:
            mail.send(msg)
            flash('Your message has been sent. Thank you!', 'success')
        except Exception as e:
            flash('Error sending message. Please try again later.', 'danger')
        return redirect(url_for('contact'))
    return render_template('contact.html', form=form)

# Serve uploaded files (gallery, protected)
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    file_record = GalleryFile.query.filter_by(stored_filename=filename).first_or_404()
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=False)

# Serve blog images (public)
@app.route('/blog-images/<filename>')
def blog_image(filename):
    return send_file(os.path.join(BLOG_IMAGES_FOLDER, filename), as_attachment=False)

# ---------- User Authentication ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed)
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

# ---------- Password Reset ----------
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
            # Don't reveal if email exists
            flash('If that email is registered, a reset link will be sent.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour
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

# ---------- Admin Panel ----------
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    tools = Tool.query.order_by(Tool.date_posted.desc()).limit(5).all()
    posts = BlogPost.query.order_by(BlogPost.date_posted.desc()).limit(5).all()
    files = GalleryFile.query.order_by(GalleryFile.upload_date.desc()).limit(5).all()
    return render_template('admin/dashboard.html', tools=tools, posts=posts, files=files)

# Tool management
@app.route('/admin/tool/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_tool():
    form = ToolForm()
    if form.validate_on_submit():
        tool = Tool(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            language=form.language.data,
            code=form.code.data,
            github_url=form.github_url.data
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

# Blog management
@app.route('/admin/blog/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_blog():
    form = BlogForm()
    if form.validate_on_submit():
        featured_image = None
        if form.featured_image.data:
            image_file = form.featured_image.data
            ext = os.path.splitext(image_file.filename)[1]
            stored_filename = str(uuid.uuid4()) + ext
            image_path = os.path.join(BLOG_IMAGES_FOLDER, stored_filename)
            image_file.save(image_path)
            featured_image = stored_filename

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
        # Handle featured image upload
        if form.featured_image.data:
            image_file = form.featured_image.data
            ext = os.path.splitext(image_file.filename)[1]
            stored_filename = str(uuid.uuid4()) + ext
            image_path = os.path.join(BLOG_IMAGES_FOLDER, stored_filename)
            image_file.save(image_path)
            # Delete old image if exists
            if post.featured_image:
                old_path = os.path.join(BLOG_IMAGES_FOLDER, post.featured_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            post.featured_image = stored_filename

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
    # Delete featured image if exists
    if post.featured_image:
        image_path = os.path.join(BLOG_IMAGES_FOLDER, post.featured_image)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(post)
    db.session.commit()
    flash('Blog post deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# Route for inline image upload (for blog content)
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

    ext = os.path.splitext(file.filename)[1]
    stored_filename = str(uuid.uuid4()) + ext
    file_path = os.path.join(BLOG_IMAGES_FOLDER, stored_filename)
    file.save(file_path)
    image_url = url_for('blog_image', filename=stored_filename, _external=True)
    return jsonify({'location': image_url})

# File upload management (gallery)
@app.route('/admin/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_file():
    form = UploadFileForm()
    if form.validate_on_submit():
        uploaded_file = form.file.data
        original_filename = secure_filename(uploaded_file.filename)
        ext = os.path.splitext(original_filename)[1]
        stored_filename = str(uuid.uuid4()) + ext
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        uploaded_file.save(save_path)
        size = os.path.getsize(save_path)

        file_record = GalleryFile(
            filename=original_filename,
            stored_filename=stored_filename,
            file_type=form.file_type.data,
            description=form.description.data,
            size=size
        )
        db.session.add(file_record)
        db.session.commit()
        flash('File uploaded successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/upload_file.html', form=form)

@app.route('/admin/file/delete/<int:id>')
@login_required
@admin_required
def delete_file(id):
    file_record = GalleryFile.query.get_or_404(id)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_record.stored_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(file_record)
    db.session.commit()
    flash('File deleted', 'success')
    return redirect(url_for('admin_dashboard'))

# Route for upload progress (dummy, progress handled client-side)
@app.route('/upload-progress', methods=['POST'])
@login_required
@admin_required
def upload_progress():
    # This is just a placeholder; actual upload handled elsewhere
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)
