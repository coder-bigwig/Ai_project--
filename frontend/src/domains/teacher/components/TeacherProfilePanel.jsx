import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 413) return '\u9644\u4ef6\u8fc7\u5927\uff0c\u8bf7\u538b\u7f29\u540e\u91cd\u8bd5\uff08\u5f53\u524d\u9650\u5236 200MB\uff09';
  return error?.response?.data?.detail || fallback;
}

function TeacherProfilePanel({ username, userRole }) {
  const [submitting, setSubmitting] = useState(false);
  const [securitySubmitting, setSecuritySubmitting] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [securityQuestionSet, setSecurityQuestionSet] = useState(false);

  const roleLabel = userRole === 'admin' ? 'System Admin' : 'Teacher Admin';

  useEffect(() => {
    let cancelled = false;

    const loadSecurityQuestion = async () => {
      if (!username) return;
      try {
        const response = await axios.get(`${API_BASE_URL}/api/auth/security-question`, {
          params: { username },
        });
        if (cancelled) return;
        const question = String(response.data?.security_question || '');
        setSecurityQuestion(question);
        setSecurityQuestionSet(Boolean(question));
      } catch (error) {
        if (cancelled) return;
        setSecurityQuestion('');
        setSecurityQuestionSet(false);
      }
    };

    loadSecurityQuestion();
    return () => {
      cancelled = true;
    };
  }, [username]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;

    if (newPassword.length < 6) {
      alert('New password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      alert('The two new passwords do not match.');
      return;
    }

    if (newPassword === currentPassword) {
      alert('New password cannot be the same as current password.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/teacher/profile/change-password`, {
        teacher_username: username,
        old_password: currentPassword,
        new_password: newPassword,
      });

      const rememberMe = localStorage.getItem('rememberMe') === 'true';
      const rememberedUsername = String(localStorage.getItem('rememberedUsername') || '').trim();
      if (rememberMe && rememberedUsername === String(username || '').trim()) {
        localStorage.setItem('rememberedPassword', newPassword);
      }

      alert(response.data?.message || '\u5bc6\u7801\u4fdd\u5b58\u6210\u529f');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      alert(getErrorMessage(error, '\u4fdd\u5b58\u5bc6\u7801\u5931\u8d25'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveSecurityQuestion = async (event) => {
    event.preventDefault();
    if (securitySubmitting) return;

    const normalizedQuestion = String(securityQuestion || '').trim();
    const normalizedAnswer = String(securityAnswer || '').trim();
    if (normalizedQuestion.length < 2) {
      alert('Security question must be at least 2 characters.');
      return;
    }
    if (normalizedAnswer.length < 2) {
      alert('Security answer must be at least 2 characters.');
      return;
    }

    setSecuritySubmitting(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/teacher/profile/security-question`, {
        teacher_username: username,
        security_question: normalizedQuestion,
        security_answer: normalizedAnswer,
      });
      alert(response.data?.message || 'Security question saved.');
      setSecurityQuestion(normalizedQuestion);
      setSecurityQuestionSet(true);
      setSecurityAnswer('');
    } catch (error) {
      alert(getErrorMessage(error, '淇濆瓨瀵嗕繚闂澶辫触'));
    } finally {
      setSecuritySubmitting(false);
    }
  };

  return (
    <div className="teacher-profile-panel">
      <div className="teacher-profile-card">
        <h3>{'\u4e2a\u4eba\u4fe1\u606f'}</h3>
        <div className="teacher-profile-grid">
          <div className="teacher-profile-item">
            <span>{'\u8d26\u53f7'}</span>
            <strong>{username || '-'}</strong>
          </div>
          <div className="teacher-profile-item">
            <span>{'\u89d2\u8272'}</span>
            <strong>{roleLabel}</strong>
          </div>
          <div className="teacher-profile-item">
            <span>{'\u5b89\u5168\u8bf4\u660e'}</span>
            <strong>{'\u4fee\u6539\u540e\u7acb\u5373\u751f\u6548'}</strong>
          </div>
          <div className="teacher-profile-item">
            <span>{'\u5bc6\u7801\u5f3a\u5ea6'}</span>
            <strong>{'\u81f3\u5c11 6 \u4f4d'}</strong>
          </div>
        </div>
      </div>

      <div className="teacher-profile-card">
        <h3>{'\u4fee\u6539\u767b\u5f55\u5bc6\u7801'}</h3>
        <form className="teacher-profile-form" onSubmit={handleSubmit}>
          <label htmlFor="teacher-current-password">{'\u5f53\u524d\u5bc6\u7801'}</label>
          <input
            id="teacher-current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
          />

          <label htmlFor="teacher-new-password">{'\u65b0\u5bc6\u7801'}</label>
          <input
            id="teacher-new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            minLength={6}
            required
          />

          <label htmlFor="teacher-confirm-password">{'\u786e\u8ba4\u65b0\u5bc6\u7801'}</label>
          <input
            id="teacher-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            minLength={6}
            required
          />

          <p className="teacher-profile-hint">{'\u4fee\u6539\u6210\u529f\u540e\uff0c\u4e0b\u6b21\u767b\u5f55\u8bf7\u4f7f\u7528\u65b0\u5bc6\u7801\u3002'}</p>
          <button type="submit" className="teacher-profile-btn" disabled={submitting}>
            {submitting ? '\u4fdd\u5b58\u4e2d...' : '\u4fdd\u5b58\u65b0\u5bc6\u7801'}
          </button>
        </form>

        <form className="teacher-profile-form" onSubmit={handleSaveSecurityQuestion}>
          <label htmlFor="teacher-security-question">{'\u5bc6\u4fdd\u95ee\u9898'}</label>
          <input
            id="teacher-security-question"
            type="text"
            value={securityQuestion}
            onChange={(event) => setSecurityQuestion(event.target.value)}
            placeholder={'\u4f8b\u5982\uff1a\u6211\u7b2c\u4e00\u95e8\u8bfe\u7a0b\u540d'}
            required
          />

          <label htmlFor="teacher-security-answer">{'\u5bc6\u4fdd\u7b54\u6848'}</label>
          <input
            id="teacher-security-answer"
            type="text"
            value={securityAnswer}
            onChange={(event) => setSecurityAnswer(event.target.value)}
            placeholder={'\u8bf7\u8f93\u5165\u5bc6\u4fdd\u7b54\u6848'}
            required
          />

          <p className="teacher-profile-hint">
            {securityQuestionSet
              ? '\u5df2\u8bbe\u7f6e\u5bc6\u4fdd\u95ee\u9898\uff0c\u53ef\u7528\u4e8e\u627e\u56de\u8d26\u53f7\u8bbf\u95ee\u6743\u9650\u3002'
              : '\u5efa\u8bae\u8bbe\u7f6e\u5bc6\u4fdd\u95ee\u9898\uff0c\u4fbf\u4e8e\u5fd8\u8bb0\u5bc6\u7801\u65f6\u81ea\u52a9\u627e\u56de\u3002'}
          </p>
          <button type="submit" className="teacher-profile-btn" disabled={securitySubmitting}>
            {securitySubmitting ? '\u4fdd\u5b58\u4e2d...' : (securityQuestionSet ? '\u66f4\u65b0\u5bc6\u4fdd\u95ee\u9898' : '\u4fdd\u5b58\u5bc6\u4fdd\u95ee\u9898')}
          </button>
        </form>
      </div>
    </div>
  );
}

export default TeacherProfilePanel;
