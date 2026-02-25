import React, { useEffect, useState } from 'react';
import axios from 'axios';

function StudentProfilePanel({ username, profile, onProfileUpdated, apiBaseUrl, text }) {
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [securitySubmitting, setSecuritySubmitting] = useState(false);
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [securityQuestion, setSecurityQuestion] = useState('');
    const [securityAnswer, setSecurityAnswer] = useState('');
    const [securityQuestionSet, setSecurityQuestionSet] = useState(false);

    useEffect(() => {
        let cancelled = false;

        const loadProfile = async () => {
            if (!username) {
                return;
            }
            setLoading(true);
            try {
                const response = await axios.get(
                    `${apiBaseUrl}/api/student/profile?student_id=${username}`
                );
                if (cancelled) {
                    return;
                }
                const data = response.data || {};
                const nextProfile = {
                    real_name: data.real_name || '',
                    class_name: data.class_name || '',
                    student_id: data.student_id || username,
                    major: data.major || data.organization || '',
                    admission_year: data.admission_year || '',
                    admission_year_label: data.admission_year_label || '',
                    security_question: data.security_question || '',
                    security_question_set: Boolean(data.security_question_set)
                };
                if (onProfileUpdated) {
                    onProfileUpdated(nextProfile);
                }
                setSecurityQuestion(nextProfile.security_question || '');
                setSecurityQuestionSet(Boolean(nextProfile.security_question_set));
                localStorage.setItem('real_name', nextProfile.real_name || '');
                localStorage.setItem('class_name', nextProfile.class_name || '');
                localStorage.setItem('student_id', nextProfile.student_id || '');
                localStorage.setItem('major', nextProfile.major || '');
                localStorage.setItem('admission_year', nextProfile.admission_year || '');
            } catch (error) {
                if (!cancelled) {
                    console.error('Failed to load student profile:', error);
                    alert(text.profileLoadError);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        loadProfile();
        return () => {
            cancelled = true;
        };
    }, [apiBaseUrl, onProfileUpdated, text.profileLoadError, username]);

    const handleChangePassword = async (event) => {
        event.preventDefault();
        if (newPassword.length < 6) {
            alert(text.passwordTooShort);
            return;
        }
        if (newPassword !== confirmPassword) {
            alert(text.passwordMismatch);
            return;
        }

        setSubmitting(true);
        try {
            const response = await axios.post(`${apiBaseUrl}/api/student/profile/change-password`, {
                student_id: username,
                old_password: currentPassword,
                new_password: newPassword
            });
            alert(response.data?.message || text.passwordChangeSuccess);
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (error) {
            alert(`${text.passwordChangeErrorPrefix}${error.response?.data?.detail || error.message}`);
        } finally {
            setSubmitting(false);
        }
    };

    const handleSaveSecurityQuestion = async (event) => {
        event.preventDefault();
        const normalizedQuestion = String(securityQuestion || '').trim();
        const normalizedAnswer = String(securityAnswer || '').trim();
        if (normalizedQuestion.length < 2) {
            alert(text.securityQuestionMinLength);
            return;
        }
        if (normalizedAnswer.length < 2) {
            alert(text.securityAnswerMinLength);
            return;
        }

        setSecuritySubmitting(true);
        try {
            const response = await axios.post(`${apiBaseUrl}/api/student/profile/security-question`, {
                student_id: username,
                security_question: normalizedQuestion,
                security_answer: normalizedAnswer
            });
            alert(response.data?.message || text.securitySaveSuccess);
            setSecurityQuestion(normalizedQuestion);
            setSecurityQuestionSet(true);
            setSecurityAnswer('');
        } catch (error) {
            alert(`${text.securitySaveErrorPrefix}${error.response?.data?.detail || error.message}`);
        } finally {
            setSecuritySubmitting(false);
        }
    };

    const majorDisplay = profile?.major || profile?.organization || '-';
    const classDisplay = profile?.class_name || '-';
    const admissionYearDisplay = profile?.admission_year_label || profile?.admission_year || '-';
    const studentIdDisplay = profile?.student_id || username || '-';

    return (
        <div className="lab-profile-panel">
            <div className="lab-profile-card">
                <h3>{text.profileInfoTitle}</h3>
                {loading ? (
                    <div className="lab-profile-loading">{text.profileLoading}</div>
                ) : (
                    <div className="lab-profile-grid">
                        <div className="lab-profile-item">
                            <span>{text.studentIdPrefix}</span>
                            <strong>{studentIdDisplay}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{text.majorPrefix}</span>
                            <strong>{majorDisplay || text.profileNotAvailable}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{text.classPrefix}</span>
                            <strong>{classDisplay || text.profileNotAvailable}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{text.admissionYearPrefix}</span>
                            <strong>{admissionYearDisplay || text.profileNotAvailable}</strong>
                        </div>
                    </div>
                )}
            </div>

            <div className="lab-profile-card lab-profile-card--security">
                <h3>{text.profileSecurityTitle}</h3>
                <div className="lab-security-layout">
                    <section className="lab-security-block">
                        <div className="lab-security-head">
                            <h4>{text.profilePasswordTitle}</h4>
                            <p>{text.profilePasswordHint}</p>
                        </div>
                        <form className="lab-password-form lab-security-form" onSubmit={handleChangePassword}>
                            <label htmlFor="current-password">{text.currentPassword}</label>
                            <input
                                id="current-password"
                                type="password"
                                autoComplete="current-password"
                                value={currentPassword}
                                onChange={(event) => setCurrentPassword(event.target.value)}
                                required
                            />

                            <label htmlFor="new-password">{text.newPassword}</label>
                            <input
                                id="new-password"
                                type="password"
                                autoComplete="new-password"
                                value={newPassword}
                                onChange={(event) => setNewPassword(event.target.value)}
                                minLength={6}
                                required
                            />

                            <label htmlFor="confirm-password">{text.confirmPassword}</label>
                            <input
                                id="confirm-password"
                                type="password"
                                autoComplete="new-password"
                                value={confirmPassword}
                                onChange={(event) => setConfirmPassword(event.target.value)}
                                minLength={6}
                                required
                            />

                            <p className="lab-password-hint">{text.passwordLengthHint}</p>
                            <button type="submit" className="lab-password-btn" disabled={submitting}>
                                {submitting ? `${text.savePassword}...` : text.savePassword}
                            </button>
                        </form>
                    </section>

                    <section className="lab-security-block">
                        <div className="lab-security-head">
                            <h4>{text.securityQuestionTitle}</h4>
                            <p>{securityQuestionSet ? text.securityQuestionConfigured : text.securityQuestionUnsetHint}</p>
                        </div>
                        <form className="lab-password-form lab-security-form lab-security-form--qa" onSubmit={handleSaveSecurityQuestion}>
                            <label htmlFor="security-question">{text.securityQuestionLabel}</label>
                            <input
                                id="security-question"
                                type="text"
                                value={securityQuestion}
                                onChange={(event) => setSecurityQuestion(event.target.value)}
                                placeholder={text.securityQuestionPlaceholder}
                                required
                            />

                            <label htmlFor="security-answer">{text.securityAnswerLabel}</label>
                            <input
                                id="security-answer"
                                type="text"
                                value={securityAnswer}
                                onChange={(event) => setSecurityAnswer(event.target.value)}
                                placeholder={text.securityAnswerPlaceholder}
                                required
                            />

                            <p className="lab-password-hint">
                                {securityQuestionSet
                                    ? text.securityQuestionUpdateHint
                                    : text.securityQuestionSetHint}
                            </p>
                            <button type="submit" className="lab-password-btn" disabled={securitySubmitting}>
                                {securitySubmitting ? text.securitySaving : (securityQuestionSet ? text.securityUpdateButton : text.securitySaveButton)}
                            </button>
                        </form>
                    </section>
                </div>
            </div>
        </div>
    );
}

export default StudentProfilePanel;
