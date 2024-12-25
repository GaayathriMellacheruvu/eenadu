import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import make_msgid

def send_email(to_email, subject, location, cleaned_text, categorized_text, location_text):
    # Your email credentials
    from_email = "techie.enthusiastic@gmail.com"
    email_password = "fhvi yrhy ibzd pebl"

    # Create the email container
    msg = MIMEMultipart('related')
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # Define the HTML email template
    logo_cid = make_msgid()  # Generate a unique Content-ID for the image
    html = f"""
    """

    # Attach the HTML body to the email
    part = MIMEText(html, 'html')
    msg.attach(part)

    # Attach the logo image
    with open("C:/Users/M.VENKATA GAAYATHRI/OneDrive/Desktop/P R A C T I C E/eenadu/logo.png", 'rb') as img_file:
        img = MIMEImage(img_file.read())
        img.add_header('Content-ID', f'<{logo_cid[1:-1]}>')
        img.add_header('Content-Disposition', 'inline', filename="logo.png")
        msg.attach(img)

    try:
        # Connect to the SMTP server
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()  # Secure the connection
        smtp_server.login(from_email, email_password)

        # Send the email
        smtp_server.sendmail(from_email, to_email, msg.as_string())

        # Close the SMTP connection
        smtp_server.quit()

        print(f"Email sent to {to_email}")

    except smtplib.SMTPException as e:
        print(f"Error sending email: {str(e)}")

# Example usage
send_email(
    to_email="mellacheruvugaayathri@gmail.com",
    subject="Test Email",
    location="Hyderabad",
    cleaned_text="This is the cleaned text.",
    categorized_text="This is the categorized text.",
    location_text="This is the location text."
)
