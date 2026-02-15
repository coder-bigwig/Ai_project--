import React, { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import axios from 'axios';
import TeacherDashboard from './TeacherDashboard';
import StudentCourseList from './StudentCourseList';
import ExperimentWorkspace from './ExperimentWorkspace';
import FloatingAIAssistant from './FloatingAIAssistant';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const AI_SESSION_TOKEN_KEY = 'aiSessionToken';
const REMEMBER_ME_KEY = 'rememberMe';
const REMEMBERED_USERNAME_KEY = 'rememberedUsername';
const REMEMBERED_PASSWORD_KEY = 'rememberedPassword';

function App() {
    const [rememberMe, setRememberMe] = useState(() => localStorage.getItem(REMEMBER_ME_KEY) === 'true');
    const [username, setUsername] = useState(() => {
        const rememberedUsername = localStorage.getItem(REMEMBERED_USERNAME_KEY);
        if (rememberedUsername) return rememberedUsername;
        return localStorage.getItem('username') || '';
    });
    const [password, setPassword] = useState(() => localStorage.getItem(REMEMBERED_PASSWORD_KEY) || '');
    const [isLoading, setIsLoading] = useState(false);
    const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('isLoggedIn'));
    const [userRole, setUserRole] = useState(() => localStorage.getItem('userRole') || null);

    const handleLogout = () => {
        [
            'username',
            'userRole',
            'isLoggedIn',
            'real_name',
            'class_name',
            'student_id',
            'organization',
            'major',
            'admission_year',
            AI_SESSION_TOKEN_KEY
        ].forEach((key) => localStorage.removeItem(key));

        const shouldRemember = localStorage.getItem(REMEMBER_ME_KEY) === 'true';
        const rememberedUsername = localStorage.getItem(REMEMBERED_USERNAME_KEY) || '';
        const rememberedPassword = localStorage.getItem(REMEMBERED_PASSWORD_KEY) || '';

        setIsLoggedIn(false);
        setUserRole(null);
        setUsername(shouldRemember ? rememberedUsername : '');
        setPassword(shouldRemember ? rememberedPassword : '');
    };

    useEffect(() => {
        if (rememberMe) {
            localStorage.setItem(REMEMBER_ME_KEY, 'true');
            return;
        }

        localStorage.setItem(REMEMBER_ME_KEY, 'false');
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
        localStorage.removeItem(REMEMBERED_PASSWORD_KEY);
    }, [rememberMe]);

    const handleLogin = async (e) => {
        e.preventDefault();

        if (!username.trim()) {
            alert('请输入账号');
            return;
        }

        setIsLoading(true);
        try {
            const loginRes = await axios.post(`${API_BASE_URL}/api/auth/login`, {
                username: username.trim(),
                password
            });

            localStorage.setItem('username', loginRes.data.username);
            localStorage.setItem('userRole', loginRes.data.role);
            localStorage.setItem('isLoggedIn', 'true');
            const aiSessionToken = String(loginRes.data.ai_session_token || '').trim();
            if (aiSessionToken) localStorage.setItem(AI_SESSION_TOKEN_KEY, aiSessionToken);
            else localStorage.removeItem(AI_SESSION_TOKEN_KEY);

            if (loginRes.data.real_name) localStorage.setItem('real_name', loginRes.data.real_name);
            else localStorage.removeItem('real_name');

            if (loginRes.data.class_name) localStorage.setItem('class_name', loginRes.data.class_name);
            else localStorage.removeItem('class_name');

            if (loginRes.data.student_id) localStorage.setItem('student_id', loginRes.data.student_id);
            else localStorage.removeItem('student_id');

            if (loginRes.data.organization) localStorage.setItem('organization', loginRes.data.organization);
            else localStorage.removeItem('organization');

            if (rememberMe) {
                localStorage.setItem(REMEMBERED_USERNAME_KEY, loginRes.data.username);
                localStorage.setItem(REMEMBERED_PASSWORD_KEY, password);
            } else {
                localStorage.removeItem(REMEMBERED_USERNAME_KEY);
                localStorage.removeItem(REMEMBERED_PASSWORD_KEY);
            }

            setUsername(loginRes.data.username);
            setUserRole(loginRes.data.role);
            setIsLoggedIn(true);
        } catch (error) {
            console.error('登录失败:', error);
            alert(error.response?.data?.detail || '登录失败，请重试');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <BrowserRouter>
            <Routes>
                <Route
                    path="/login"
                    element={
                        !isLoggedIn ? (
                            <LoginView
                                username={username}
                                setUsername={setUsername}
                                password={password}
                                setPassword={setPassword}
                                rememberMe={rememberMe}
                                setRememberMe={setRememberMe}
                                handleLogin={handleLogin}
                                isLoading={isLoading}
                            />
                        ) : (
                            <Navigate to="/" replace />
                        )
                    }
                />
                <Route
                    path="/workspace/:experimentId"
                    element={isLoggedIn ? <ExperimentWorkspace /> : <Navigate to="/login" replace />}
                />
                <Route
                    path="/"
                    element={
                        isLoggedIn ? (
                            (userRole === 'teacher' || userRole === 'admin') ? (
                                <TeacherDashboard username={username} userRole={userRole} onLogout={handleLogout} />
                            ) : (
                                <StudentCourseList username={username} onLogout={handleLogout} />
                            )
                        ) : (
                            <Navigate to="/login" replace />
                        )
                    }
                />
            </Routes>
            {isLoggedIn && <FloatingAIAssistant />}
        </BrowserRouter>
    );
}

function LoginView({
    username,
    setUsername,
    password,
    setPassword,
    rememberMe,
    setRememberMe,
    handleLogin,
    isLoading
}) {
    const [forgotOpen, setForgotOpen] = useState(false);

    const handleResetSuccess = (resetUsername, resetPassword) => {
        setUsername(resetUsername);
        setPassword(resetPassword);
    };

    return (
        <div className="simple-login-container">
            <div className="simple-login-card">
                <div className="simple-login-header">
                    <h1>福州理工学院 AI 编程实践教学平台</h1>
                </div>

                <form onSubmit={handleLogin} className="simple-login-form">
                    <div className="simple-form-group">
                        <label>账号</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="请输入账号"
                            disabled={isLoading}
                        />
                    </div>

                    <div className="simple-form-group">
                        <label>密码</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="请输入密码"
                            disabled={isLoading}
                        />
                    </div>

                    <div className="simple-form-remember">
                        <label>
                            <input
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                disabled={isLoading}
                            />
                            <span>记住密码</span>
                        </label>
                    </div>

                    <button
                        type="button"
                        className="simple-forgot-btn"
                        onClick={() => setForgotOpen(true)}
                        disabled={isLoading}
                    >
                        忘记密码？
                    </button>

                    <button type="submit" className="simple-login-btn" disabled={isLoading}>
                        {isLoading ? '登录中...' : '登录'}
                    </button>
                </form>
            </div>

            <ForgotPasswordDialog
                open={forgotOpen}
                initialUsername={username}
                onClose={() => setForgotOpen(false)}
                onResetSuccess={handleResetSuccess}
            />
        </div>
    );
}

function ForgotPasswordDialog({ open, initialUsername, onClose, onResetSuccess }) {
    const [username, setUsername] = useState('');
    const [securityQuestion, setSecurityQuestion] = useState('');
    const [securityAnswer, setSecurityAnswer] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        if (!open) {
            setUsername('');
            setSecurityQuestion('');
            setSecurityAnswer('');
            setNewPassword('');
            setConfirmPassword('');
            setSubmitting(false);
            return;
        }
        setUsername(String(initialUsername || '').trim());
    }, [initialUsername, open]);

    const loadSecurityQuestion = async () => {
        const account = String(username || '').trim();
        if (!account) {
            alert('请输入账号');
            return;
        }

        setSubmitting(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/auth/security-question`, {
                params: { username: account }
            });
            setSecurityQuestion(response.data?.security_question || '');
        } catch (error) {
            setSecurityQuestion('');
            alert(error.response?.data?.detail || '获取密保问题失败');
        } finally {
            setSubmitting(false);
        }
    };

    const resetPassword = async () => {
        const account = String(username || '').trim();
        if (!account) {
            alert('请输入账号');
            return;
        }
        if (!securityQuestion) {
            alert('请先获取密保问题');
            return;
        }
        if (newPassword.length < 6) {
            alert('新密码长度不能少于6位');
            return;
        }
        if (newPassword !== confirmPassword) {
            alert('两次输入的新密码不一致');
            return;
        }

        setSubmitting(true);
        try {
            const response = await axios.post(`${API_BASE_URL}/api/auth/forgot-password-reset`, {
                username: account,
                security_answer: securityAnswer,
                new_password: newPassword
            });
            alert(response.data?.message || '密码重置成功');
            if (typeof onResetSuccess === 'function') {
                onResetSuccess(account, newPassword);
            }
            onClose();
        } catch (error) {
            alert(error.response?.data?.detail || '密码重置失败');
        } finally {
            setSubmitting(false);
        }
    };

    if (!open) return null;

    return (
        <div className="simple-forgot-overlay" onClick={onClose}>
            <div className="simple-forgot-dialog" onClick={(event) => event.stopPropagation()}>
                <h3>找回密码</h3>

                <label htmlFor="forgot-username">账号</label>
                <div className="simple-forgot-row">
                    <input
                        id="forgot-username"
                        type="text"
                        value={username}
                        onChange={(event) => setUsername(event.target.value)}
                        placeholder="请输入学生/教师账号"
                        disabled={submitting}
                    />
                    <button type="button" onClick={loadSecurityQuestion} disabled={submitting}>
                        获取密保问题
                    </button>
                </div>

                {securityQuestion ? (
                    <>
                        <label htmlFor="forgot-question">密保问题</label>
                        <input id="forgot-question" type="text" value={securityQuestion} readOnly />

                        <label htmlFor="forgot-answer">密保答案</label>
                        <input
                            id="forgot-answer"
                            type="text"
                            value={securityAnswer}
                            onChange={(event) => setSecurityAnswer(event.target.value)}
                            placeholder="请输入密保答案"
                            disabled={submitting}
                        />

                        <label htmlFor="forgot-new-password">新密码</label>
                        <input
                            id="forgot-new-password"
                            type="password"
                            value={newPassword}
                            onChange={(event) => setNewPassword(event.target.value)}
                            placeholder="至少6位"
                            minLength={6}
                            disabled={submitting}
                        />

                        <label htmlFor="forgot-confirm-password">确认新密码</label>
                        <input
                            id="forgot-confirm-password"
                            type="password"
                            value={confirmPassword}
                            onChange={(event) => setConfirmPassword(event.target.value)}
                            placeholder="再次输入新密码"
                            minLength={6}
                            disabled={submitting}
                        />
                    </>
                ) : null}

                <div className="simple-forgot-actions">
                    <button type="button" className="secondary" onClick={onClose} disabled={submitting}>
                        取消
                    </button>
                    <button type="button" onClick={resetPassword} disabled={submitting || !securityQuestion}>
                        {submitting ? '处理中...' : '重置密码'}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default App;
