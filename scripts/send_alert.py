#!/usr/bin/env python3
import os
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, content):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receivers = os.getenv("EMAIL_RECEIVERS", "").split(',')
    if not sender or not password or not receivers:
        print("邮件配置缺失")
        return
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ','.join(receivers)
    try:
        with smtplib.SMTP_SSL('smtp.qq.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("告警邮件已发送")
    except Exception as e:
        print(f"发送失败: {e}")

if __name__ == "__main__":
    error = os.getenv("ERROR_MSG", "流水线执行失败")
    send_alert("量化系统告警", error)