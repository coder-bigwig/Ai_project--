import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminUserManagementLegacy from './AdminUserManagementLegacy';
import AdminResourceControl from './AdminResourceControl';
import TeacherAIModule from '../../teacher/components/TeacherAIModule';
import TeacherProfilePanel from '../../teacher/components/TeacherProfilePanel';
import '../../teacher/styles/TeacherDashboard.css';

const TABS = [
  { key: 'admin-resource', label: '资源控制', tip: '配额与操作日志', Icon: AdminControlTabIcon },
  { key: 'admin-user-management', label: '用户管理', tip: '教师与学生', Icon: UserManagementTabIcon },
  { key: 'admin-profile', label: '个人中心', tip: '账号与安全设置', Icon: ProfileTabIcon },
  { key: 'admin-ai', label: 'AI功能', tip: '模型与密钥配置', Icon: AITabIcon },
];

function AdminDashboard({ username, onLogout }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('admin-resource');
  const currentTab = useMemo(() => TABS.find((item) => item.key === activeTab) || TABS[0], [activeTab]);

  const logout = () => {
    if (typeof onLogout === 'function') {
      onLogout();
      navigate('/login', { replace: true });
      return;
    }

    [
      'username',
      'userRole',
      'isLoggedIn',
      'real_name',
      'class_name',
      'student_id',
      'organization',
    ].forEach((key) => localStorage.removeItem(key));
    window.location.reload();
  };

  return (
    <div className="teacher-lab-shell admin-lab-shell">
      <header className="teacher-lab-topbar">
        <div className="teacher-lab-brand">
          <h1>福州理工学院AI编程实践教学平台</h1>
          <p>管理员控制台 / AI Programming Practice Teaching Platform</p>
        </div>
        <div className="teacher-lab-user">
          <span className="teacher-lab-avatar">{(username || 'A').slice(0, 1).toUpperCase()}</span>
          <div className="teacher-lab-user-text">
            <span className="teacher-lab-user-name">{`管理员账号：${username || '-'}`}</span>
            <span className="teacher-lab-user-role">角色：系统管理员</span>
          </div>
          <button type="button" className="teacher-lab-logout" onClick={logout}>退出</button>
        </div>
      </header>

      <div className="teacher-lab-layout">
        <aside className="teacher-lab-sidebar">
          <div className="teacher-lab-sidebar-title">模块</div>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`teacher-lab-menu-item ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span className="teacher-lab-menu-icon"><tab.Icon /></span>
              <span className="teacher-lab-menu-text"><strong>{tab.label}</strong><small>{tab.tip}</small></span>
            </button>
          ))}
        </aside>

        <section className="teacher-lab-content">
          <div className="teacher-lab-breadcrumb">管理员端 / <strong>{currentTab.label}</strong></div>

          {activeTab === 'admin-user-management' ? (
            <div className="teacher-lab-section">
              <AdminUserManagementLegacy username={username} userRole="admin" />
            </div>
          ) : null}

          {activeTab === 'admin-resource' ? (
            <div className="teacher-lab-section">
              <AdminResourceControl username={username} />
            </div>
          ) : null}

          {activeTab === 'admin-ai' ? (
            <div className="teacher-lab-section">
              <TeacherAIModule username={username} />
            </div>
          ) : null}

          {activeTab === 'admin-profile' ? (
            <div className="teacher-lab-section">
              <TeacherProfilePanel username={username} userRole="admin" />
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function UserManagementTabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="8.5" r="2.5" />
      <circle cx="16.5" cy="9.5" r="2" />
      <path d="M4.5 18.5C5.2 15.9 7 14.3 9.4 14.3c2.3 0 4.1 1.4 4.9 3.9" />
      <path d="M14 15.8c.6-1.7 1.8-2.7 3.5-2.7 1.8 0 3.1 1.1 3.8 3.1" />
    </svg>
  );
}

function AdminControlTabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6h16M4 12h16M4 18h16" />
      <circle cx="7" cy="6" r="1.5" />
      <circle cx="17" cy="12" r="1.5" />
      <circle cx="10" cy="18" r="1.5" />
    </svg>
  );
}

function ProfileTabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 18.5C6.6 15.9 9 14.4 12 14.4C15 14.4 17.4 15.9 18.5 18.5" />
      <rect x="3.5" y="3.5" width="17" height="17" rx="2.4" />
    </svg>
  );
}

function AITabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v4M6.5 5.5l2.8 2.8M3 12h4M17 12h4M6.5 18.5l2.8-2.8M14.7 15.7l2.8 2.8" />
      <circle cx="12" cy="12" r="5" />
      <path d="M10.5 12.2l1 1 2-2.3" />
    </svg>
  );
}

export default AdminDashboard;
