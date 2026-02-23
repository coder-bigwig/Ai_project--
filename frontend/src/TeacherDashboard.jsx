import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import TeacherReview from './TeacherReview';
import TeacherUserManagement from './TeacherUserManagement';
import LegacyTeacherUserManagement from './LegacyTeacherUserManagement';
import TeacherTeamManagement from './TeacherTeamManagement';
import OfferingDetail from './OfferingDetail';
import ResourceFileManagement from './ResourceFileManagement';
import TeacherAIModule from './TeacherAIModule';
import AdminResourceControl from './AdminResourceControl';
import { persistJupyterTokenFromUrl } from './jupyterAuth';
import cover01 from './assets/system-covers/cover-01.svg';
import cover02 from './assets/system-covers/cover-02.svg';
import cover03 from './assets/system-covers/cover-03.svg';
import './TeacherDashboard.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const TEACHER_COURSE_RESUME_KEY = 'teacherCourseResumeId';
const OFFERING_COVER_STORAGE_KEY = 'offeringSystemCoverMap';
const JUPYTERHUB_URL = process.env.REACT_APP_JUPYTERHUB_URL || '';
const DEFAULT_JUPYTERHUB_URL = `${window.location.origin}/jupyter/hub/home`;
const DEFAULT_JUPYTERHUB_HEALTH_URL = `${window.location.origin}/jupyter/hub/health`;
const LEGACY_JUPYTERHUB_URL = `${window.location.protocol}//${window.location.hostname}:8003/jupyter/hub/home`;
const SYSTEM_COVERS = [
  { id: 'system-01', label: '绯荤粺灏侀潰 1', src: cover01 },
  { id: 'system-02', label: '绯荤粺灏侀潰 2', src: cover02 },
  { id: 'system-03', label: '绯荤粺灏侀潰 3', src: cover03 },
];

const TABS = [
  { key: 'courses', label: '\u8bfe\u7a0b\u5e93', tip: '\u8bfe\u7a0b\u4e0e\u5b9e\u9a8c\u7ba1\u7406', Icon: CourseTabIcon },
  { key: 'profile', label: '\u4e2a\u4eba\u4e2d\u5fc3', tip: '\u8d26\u53f7\u4e0e\u5b89\u5168\u8bbe\u7f6e', Icon: ProfileTabIcon },
  { key: 'ai', label: 'AI\u529f\u80fd', tip: '\u6a21\u578b\u4e0e\u5bc6\u94a5\u914d\u7f6e', Icon: AITabIcon },
];

const ADMIN_TAB = {
  key: 'admin-resource',
  label: '\u8d44\u6e90\u76d1\u63a7',
  tip: '\u5bb9\u5668\u914d\u989d\u4e0e\u65e5\u5fd7',
  Icon: AdminControlTabIcon,
};

const ADMIN_USER_TAB = {
  key: 'admin-user-management',
  label: '\u7528\u6237\u7ba1\u7406',
  tip: '\u6559\u5e08\u4e0e\u5b66\u751f\u8d26\u53f7\u7ba1\u7406',
  Icon: UserManagementTabIcon,
};

function formatDate(v) {
  if (!v) return '-';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '-';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function formatDateTime(v) {
  if (!v) return '-';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '-';
  return `${formatDate(v)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function toNumericScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? score : null;
}

function formatScoreValue(value) {
  const score = toNumericScore(value);
  if (score === null) return '';
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (/[",\r\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function progressStatusKey(status) {
  const v = String(status || '').toLowerCase();
  if (v.includes('\u8bc4\u5206') || v.includes('graded')) return 'graded';
  if (v.includes('\u63d0\u4ea4') || v.includes('submit')) return 'submitted';
  if (v.includes('\u8fdb\u884c') || v.includes('progress')) return 'in-progress';
  return 'not-started';
}

function isCompleted(status) {
  const key = progressStatusKey(status);
  return key === 'submitted' || key === 'graded';
}

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 413) return '\u9644\u4ef6\u8fc7\u5927\uff0c\u8bf7\u538b\u7f29\u540e\u91cd\u8bd5\uff08\u5f53\u524d\u9650\u5236 200MB\uff09';
  return error?.response?.data?.detail || fallback;
}

function isRouteMissingError(error) {
  const status = Number(error?.response?.status || 0);
  if (status !== 404 && status !== 405) return false;
  const detail = String(error?.response?.data?.detail || '').trim().toLowerCase();
  if (status === 405) return !detail || detail === 'method not allowed';
  return !detail || detail === 'not found';
}

function parseTags(v) {
  return String(v || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
}

function normalizeStringArray(values) {
  if (!Array.isArray(values)) return [];
  const seen = new Set();
  const result = [];
  values.forEach((item) => {
    const normalized = String(item || '').trim();
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) return;
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function normalizePublishScope(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'class' || normalized === 'student') return normalized;
  return 'all';
}

function loadCoverSelectionMap() {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(localStorage.getItem(OFFERING_COVER_STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    return {};
  }
}

function hashString(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function resolveCourseName(item) {
  const explicit = String(item?.course_name || '').trim();
  if (explicit) return explicit;
  const path = String(item?.notebook_path || '').trim();
  const first = path.split('/').filter(Boolean)[0] || '';
  if (first && first.toLowerCase() !== 'course') return first;
  return '\u9ed8\u8ba4\u8bfe\u7a0b';
}

function normalizeTeacherCourses(items) {
  if (!Array.isArray(items)) return [];
  const hasCourseShape = items.some((item) => Array.isArray(item?.experiments) || item?.name);

  if (hasCourseShape) {
    return items
      .map((item) => {
        const experiments = Array.isArray(item?.experiments)
          ? [...item.experiments].sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
          : [];
        return {
          id: item?.id,
          name: item?.name || '\u672a\u547d\u540d\u8bfe\u7a0b',
          description: item?.description || '',
          created_by: item?.created_by || '',
          created_at: item?.created_at || null,
          updated_at: item?.updated_at || item?.latest_experiment_at || item?.created_at || null,
          experiment_count: Number(item?.experiment_count ?? experiments.length),
          published_count: Number(item?.published_count ?? experiments.filter((exp) => exp?.published).length),
          tags: Array.isArray(item?.tags) ? item.tags : [],
          experiments,
        };
      })
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime());
  }

  const grouped = new Map();
  items.forEach((exp) => {
    const name = resolveCourseName(exp);
    const key = name.toLowerCase();
    const cur = grouped.get(key) || {
      id: `legacy-${key}`,
      name,
      description: '',
      created_by: exp?.created_by || '',
      created_at: exp?.created_at || null,
      updated_at: exp?.created_at || null,
      experiment_count: 0,
      published_count: 0,
      tags: new Set(),
      experiments: [],
    };
    cur.experiments.push(exp);
    cur.experiment_count += 1;
    if (exp?.published) cur.published_count += 1;
    (exp?.tags || []).forEach((tag) => tag && cur.tags.add(tag));
    if ((exp?.created_at || '') > (cur.updated_at || '')) cur.updated_at = exp.created_at;
    grouped.set(key, cur);
  });

  return Array.from(grouped.values())
    .map((item) => ({
      ...item,
      tags: Array.from(item.tags),
      experiments: item.experiments.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()),
    }))
    .sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime());
}

function flattenExperiments(courses) {
  const rows = [];
  (courses || []).forEach((course) => {
    (course?.experiments || []).forEach((exp) => rows.push(exp));
  });
  return rows;
}

function TeacherDashboard({ username, userRole, onLogout }) {
  const navigate = useNavigate();
  const isAdmin = userRole === 'admin' || String(username || '').trim() === 'admin';
  const tabs = useMemo(() => (isAdmin ? [...TABS, ADMIN_USER_TAB, ADMIN_TAB] : TABS), [isAdmin]);
  const [activeTab, setActiveTab] = useState(isAdmin ? 'admin-resource' : 'courses');
  const [courses, setCourses] = useState([]);
  const [progress, setProgress] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loadingCourses, setLoadingCourses] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);

  const [showCourseEditor, setShowCourseEditor] = useState(false);
  const [editingCourse, setEditingCourse] = useState(null);
  const [showExperimentEditor, setShowExperimentEditor] = useState(false);
  const [editingExperiment, setEditingExperiment] = useState(null);
  const [targetCourse, setTargetCourse] = useState(null);

  const currentTab = tabs.find((item) => item.key === activeTab) || tabs[0];

  const loadCourses = useCallback(async () => {
    setLoadingCourses(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/teacher/courses`, { params: { teacher_username: username } });
      setCourses(normalizeTeacherCourses(res.data));
    } catch (error) {
      console.error('loadCourses failed', error);
      alert(getErrorMessage(error, '\u52a0\u8f7d\u8bfe\u7a0b\u5e93\u5931\u8d25'));
      setCourses([]);
    } finally {
      setLoadingCourses(false);
    }
  }, [username]);

  const loadProgress = useCallback(async () => {
    setLoadingProgress(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/teacher/progress`, { params: { teacher_username: username } });
      setProgress(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error('loadProgress failed', error);
      alert(getErrorMessage(error, '\u52a0\u8f7d\u5b66\u751f\u8fdb\u5ea6\u5931\u8d25'));
      setProgress([]);
    } finally {
      setLoadingProgress(false);
    }
  }, [username]);

    const loadSubmissions = useCallback(async (targetExperimentIds = null) => {
    setLoadingSubmissions(true);
    try {
      let experimentIds = Array.isArray(targetExperimentIds)
        ? targetExperimentIds.map((item) => String(item || '').trim()).filter(Boolean)
        : [];

      if (experimentIds.length === 0 && targetExperimentIds === null) {
        const source = courses.length > 0
          ? courses
          : normalizeTeacherCourses((await axios.get(`${API_BASE_URL}/api/teacher/courses`, { params: { teacher_username: username } })).data || []);
        experimentIds = source.flatMap((course) => (course?.experiments || []).map((exp) => exp.id)).filter(Boolean);
      }

      if (experimentIds.length === 0) {
        setSubmissions([]);
        return;
      }

      const lists = await Promise.all(
        experimentIds.map((id) =>
          axios
            .get(`${API_BASE_URL}/api/teacher/experiments/${id}/submissions`)
            .then((res) => (Array.isArray(res.data) ? res.data : []))
            .catch(() => [])
        )
      );
      setSubmissions(lists.flat());
    } catch (error) {
      console.error('loadSubmissions failed', error);
      alert(getErrorMessage(error, '\u52a0\u8f7d\u63d0\u4ea4\u8bb0\u5f55\u5931\u8d25'));
      setSubmissions([]);
    } finally {
      setLoadingSubmissions(false);
    }
  }, [courses, username]);

    useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  const handleGrade = async (submissionId, score, comment) => {
    try {
      await axios.post(`${API_BASE_URL}/api/teacher/grade/${submissionId}`, null, {
        params: { score, comment, teacher_username: username },
      });
      alert('评分成功');
    } catch (error) {
      console.error('grade failed', error);
      alert(getErrorMessage(error, '评分失败'));
    }
  };

  const handleCreateCourse = async (formData) => {
    const payload = {
      name: String(formData.name || '').trim(),
      description: String(formData.description || '').trim(),
      teacher_username: username,
    };
    const res = await axios.post(`${API_BASE_URL}/api/teacher/courses`, payload);
    await loadCourses();
    return res.data;
  };

  const handleUpdateCourse = async (course, formData) => {
    const payload = {
      name: String(formData.name || '').trim(),
      description: String(formData.description || '').trim(),
      teacher_username: username,
    };
    const res = await axios.patch(`${API_BASE_URL}/api/teacher/courses/${course.id}`, payload);
    await loadCourses();
    return res.data;
  };

  const handleDeleteCourse = async (course) => {
    const courseId = String(course?.id || '').trim();
    if (!courseId) return false;
    const courseName = String(course?.name || '\u8be5\u8bfe\u7a0b').trim() || '\u8be5\u8bfe\u7a0b';
    if (!window.confirm(`\u786e\u5b9a\u5220\u9664\u8bfe\u7a0b "${courseName}" \u5417\uff1f`)) return false;

    try {
      await axios.delete(`${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}`, {
        params: { teacher_username: username },
      });
    } catch (error) {
      const status = Number(error?.response?.status || 0);
      if (status !== 409) throw error;
      if (!window.confirm(`\u8bfe\u7a0b "${courseName}" \u4e0b\u5b58\u5728\u4f5c\u4e1a\uff0c\u662f\u5426\u8fde\u540c\u4f5c\u4e1a\u4e0e\u9644\u4ef6\u4e00\u5e76\u5220\u9664\uff1f\u8be5\u64cd\u4f5c\u4e0d\u53ef\u6062\u590d\u3002`)) {
        return false;
      }
      await axios.delete(`${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}`, {
        params: { teacher_username: username, delete_experiments: true },
      });
    }

    await loadCourses();
    alert('\u8bfe\u7a0b\u5df2\u5220\u9664');
    return true;
  };

  const buildExperimentPayload = (experiment, formData, course) => ({
    ...experiment,
    title: formData.title,
    description: formData.description,
    difficulty: formData.difficulty,
    tags: parseTags(formData.tags),
    notebook_path: formData.notebook_path,
    published: Boolean(formData.published),
    publish_scope: normalizePublishScope(formData.publish_scope ?? experiment.publish_scope),
    target_class_names: normalizeStringArray(formData.target_class_names ?? experiment.target_class_names),
    target_student_ids: normalizeStringArray(formData.target_student_ids ?? experiment.target_student_ids),
    course_id: course.id,
    course_name: course.name,
    created_by: experiment.created_by || username,
    created_at: experiment.created_at || new Date().toISOString(),
    resources: experiment.resources || { cpu: 1.0, memory: '2G', storage: '1G' },
  });

  const handleCreateExperiment = async (course, formData) => {
    const payload = {
      title: formData.title,
      description: formData.description,
      difficulty: formData.difficulty,
      tags: parseTags(formData.tags),
      notebook_path: formData.notebook_path,
      published: Boolean(formData.published),
      publish_scope: normalizePublishScope(formData.publish_scope),
      target_class_names: normalizeStringArray(formData.target_class_names),
      target_student_ids: normalizeStringArray(formData.target_student_ids),
      course_id: course.id,
      course_name: course.name,
      created_by: username,
    };
    const res = await axios.post(`${API_BASE_URL}/api/experiments`, payload);
    await loadCourses();
    return res.data;
  };

  const handleUpdateExperiment = async (course, experiment, formData) => {
    const payload = buildExperimentPayload(experiment, formData, course);
    const res = await axios.put(`${API_BASE_URL}/api/experiments/${experiment.id}`, payload);
    await loadCourses();
    return res.data;
  };

  const handleDeleteExperiment = async (course, experiment) => {
    const targetTitle = String(experiment?.title || '\u8be5\u4f5c\u4e1a');
    if (!window.confirm(`\u786e\u5b9a\u5220\u9664\u4f5c\u4e1a "${targetTitle}" \u5417\uff1f`)) return false;
    await axios.delete(`${API_BASE_URL}/api/experiments/${experiment.id}`, {
      params: { teacher_username: username },
    });
    await loadCourses();
    alert('\u4f5c\u4e1a\u5df2\u5220\u9664\uff0c\u53ef\u572830\u5929\u5185\u5728\u56de\u6536\u7ad9\u6062\u590d');
    return true;
  };

  const handleListRecycleExperiments = async (courseId) => {
    const res = await axios.get(`${API_BASE_URL}/api/teacher/experiments/recycle`, {
      params: { teacher_username: username, course_id: courseId },
    });
    return Array.isArray(res.data?.items) ? res.data.items : [];
  };

  const handleRestoreExperiment = async (experimentId) => {
    await axios.post(`${API_BASE_URL}/api/teacher/experiments/${experimentId}/restore`, null, {
      params: { teacher_username: username },
    });
    await loadCourses();
  };

  const handlePermanentDeleteExperiment = async (experimentId) => {
    const requestOptions = { params: { teacher_username: username } };
    const candidates = [
      { method: 'delete', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent-delete` },
      { method: 'post', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent-delete` },
      { method: 'delete', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent_delete` },
      { method: 'post', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent_delete` },
      { method: 'delete', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent-delete/` },
      { method: 'post', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent-delete/` },
      { method: 'delete', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent_delete/` },
      { method: 'post', url: `${API_BASE_URL}/api/teacher/experiments/${experimentId}/permanent_delete/` },
    ];

    let lastError = null;
    for (const candidate of candidates) {
      try {
        if (candidate.method === 'delete') {
          await axios.delete(candidate.url, requestOptions);
        } else {
          await axios.post(candidate.url, null, requestOptions);
        }
        await loadCourses();
        return;
      } catch (error) {
        if (isRouteMissingError(error)) {
          lastError = error;
          continue;
        }
        throw error;
      }
    }

    if (lastError) {
      const compatibilityError = new Error('permanent delete endpoint not found');
      compatibilityError.response = {
        data: {
          detail: '\u5f53\u524d\u540e\u7aef\u672a\u63d0\u4f9b\u201c\u5f7b\u5e95\u5220\u9664\u201d\u63a5\u53e3\uff0c\u8bf7\u91cd\u5efa\u5e76\u91cd\u542f\u540e\u7aef\u670d\u52a1\u540e\u518d\u8bd5',
        },
      };
      throw compatibilityError;
    }

    throw new Error('permanent delete failed');
  };

  const experiments = useMemo(() => flattenExperiments(courses), [courses]);
  const courseMap = useMemo(() => {
    const map = {};
    experiments.forEach((exp) => {
      map[exp.id] = exp;
    });
    return map;
  }, [experiments]);

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

  const openJupyterHub = async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/api/jupyterhub/auto-login-url`, { params: { username } });
      const autoLoginUrl = resp?.data?.jupyter_url;
      if (autoLoginUrl) {
        const launchUrl = persistJupyterTokenFromUrl(autoLoginUrl);
        window.open(launchUrl, '_blank', 'noopener,noreferrer');
        return;
      }
    } catch (err) {
      // fallback to below
    }

    if (JUPYTERHUB_URL) {
      window.open(JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
      return;
    }

    try {
      const resp = await fetch(DEFAULT_JUPYTERHUB_HEALTH_URL, { method: 'GET', credentials: 'omit' });
      if (resp.ok) {
        window.open(DEFAULT_JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
        return;
      }
    } catch (err) {
      // ignore
    }

    window.open(LEGACY_JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="teacher-lab-shell">
      <header className="teacher-lab-topbar">
        <div className="teacher-lab-brand">
          <h1>{'\u798f\u5dde\u7406\u5de5\u5b66\u9662AI\u7f16\u7a0b\u5b9e\u8df5\u6559\u5b66\u5e73\u53f0'}</h1>
          <p>{'\u6559\u5e08\u7ba1\u7406\u7aef'} / AI Programming Practice Teaching Platform</p>
        </div>
        <div className="teacher-lab-user">
          <span className="teacher-lab-avatar">{(username || 'T').slice(0, 1).toUpperCase()}</span>
          <div className="teacher-lab-user-text">
            <span className="teacher-lab-user-name">{`\u6559\u5e08\u8d26\u53f7\uff1a${username || '-'}`}</span>
            <span className="teacher-lab-user-role">{`\u89d2\u8272\uff1a${isAdmin ? '\u7cfb\u7edf\u7ba1\u7406\u5458' : '\u6559\u5e08\u7ba1\u7406\u5458'}`}</span>
          </div>
          <button type="button" className="teacher-lab-jhub" onClick={openJupyterHub}>{'\u8fdb\u5165 JupyterHub'}</button>
          <button type="button" className="teacher-lab-logout" onClick={logout}>{'\u9000\u51fa'}</button>
        </div>
      </header>

      <div className="teacher-lab-layout">
        <aside className="teacher-lab-sidebar">
          <div className="teacher-lab-sidebar-title">{'\u6a21\u5757'}</div>
          {tabs.map((tab) => (
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
          {activeTab === 'courses' ? null : <div className="teacher-lab-breadcrumb">{'\u6559\u5e08\u7aef'} / <strong>{currentTab.label}</strong></div>}

          {activeTab === 'courses' ? (
            <CourseWorkspacePanel
              username={username}
              userRole={userRole}
              courses={courses}
              loading={loadingCourses}
              progress={progress}
              loadingProgress={loadingProgress}
              onLoadProgress={loadProgress}
              submissions={submissions}
              loadingSubmissions={loadingSubmissions}
              onLoadSubmissions={loadSubmissions}
              onGradeSubmission={handleGrade}
              courseMap={courseMap}
              onCreateCourse={() => {
                setEditingCourse(null);
                setShowCourseEditor(true);
              }}
              onDeleteCourse={handleDeleteCourse}
              onCreateExperiment={(course) => {
                setTargetCourse(course);
                setEditingExperiment(null);
                setShowExperimentEditor(true);
              }}
              onEditExperiment={(course, experiment) => {
                setTargetCourse(course);
                setEditingExperiment(experiment);
                setShowExperimentEditor(true);
              }}
              onDeleteExperiment={handleDeleteExperiment}
              onListRecycleExperiments={handleListRecycleExperiments}
              onRestoreExperiment={handleRestoreExperiment}
              onPermanentDeleteExperiment={handlePermanentDeleteExperiment}
            />
          ) : null}

          {activeTab === 'profile' ? (
            <div className="teacher-lab-section">
              <TeacherProfilePanel username={username} userRole={userRole} />
            </div>
          ) : null}

          {activeTab === 'ai' ? (
            <div className="teacher-lab-section">
              <TeacherAIModule username={username} />
            </div>
          ) : null}

          {activeTab === 'admin-user-management' ? (
            <div className="teacher-lab-section">
              <LegacyTeacherUserManagement username={username} userRole={userRole} />
            </div>
          ) : null}

          {activeTab === 'admin-resource' ? (
            <div className="teacher-lab-section">
              <AdminResourceControl username={username} />
            </div>
          ) : null}
        </section>
      </div>

      {showCourseEditor ? (
        <CourseEditorModal
          initialCourse={editingCourse}
          onClose={() => {
            setShowCourseEditor(false);
            setEditingCourse(null);
          }}
          onCreate={handleCreateCourse}
          onUpdate={handleUpdateCourse}
        />
      ) : null}

      {showExperimentEditor && targetCourse ? (
        <ExperimentEditorModal
          username={username}
          course={targetCourse}
          initialExperiment={editingExperiment}
          onClose={() => {
            setShowExperimentEditor(false);
            setEditingExperiment(null);
            setTargetCourse(null);
          }}
          onCreate={handleCreateExperiment}
          onUpdate={handleUpdateExperiment}
        />
      ) : null}
    </div>
  );
}

function CourseWorkspacePanel({
  username,
  userRole,
  courses,
  loading,
  progress,
  loadingProgress,
  onLoadProgress,
  submissions,
  loadingSubmissions,
  onLoadSubmissions,
  onGradeSubmission,
  courseMap,
  onCreateCourse,
  onDeleteCourse,
  onCreateExperiment,
  onEditExperiment,
  onDeleteExperiment,
  onListRecycleExperiments,
  onRestoreExperiment,
  onPermanentDeleteExperiment,
}) {
  const [resumeCourseId] = useState(() => {
    const cachedCourseId = String(sessionStorage.getItem(TEACHER_COURSE_RESUME_KEY) || '').trim();
    if (cachedCourseId) sessionStorage.removeItem(TEACHER_COURSE_RESUME_KEY);
    return cachedCourseId;
  });
  const [viewMode, setViewMode] = useState(resumeCourseId ? 'detail' : 'home');
  const [selectedCourseId, setSelectedCourseId] = useState(resumeCourseId);
  const [homeKeyword, setHomeKeyword] = useState('');
  const [detailMenu, setDetailMenu] = useState('management');
  const [assignmentKeyword, setAssignmentKeyword] = useState('');
  const [loadingRecycle, setLoadingRecycle] = useState(false);
  const [recycleRows, setRecycleRows] = useState([]);
  const [activeManageTab, setActiveManageTab] = useState('class-management');
  const [allOfferings, setAllOfferings] = useState([]);
  const [coverSelectionMap, setCoverSelectionMap] = useState(() => loadCoverSelectionMap());
  const [selectedCourseStudentCount, setSelectedCourseStudentCount] = useState(0);
  const [selectedCourseClassNames, setSelectedCourseClassNames] = useState([]);
  const [summaryRefreshTick, setSummaryRefreshTick] = useState(0);
  const [statisticsTab, setStatisticsTab] = useState('overview');
  const [statisticsExperimentId, setStatisticsExperimentId] = useState('all');
  const [statisticsKeyword, setStatisticsKeyword] = useState('');
  const [statisticsStudents, setStatisticsStudents] = useState([]);
  const [loadingStatisticsStudents, setLoadingStatisticsStudents] = useState(false);

  const selectedCourse = useMemo(() => {
    const needle = String(selectedCourseId || '').trim();
    if (!needle) return null;
    return (courses || []).find((item) => String(item?.id || '').trim() === needle) || null;
  }, [courses, selectedCourseId]);

  const selectedCourseExperiments = useMemo(
    () => (Array.isArray(selectedCourse?.experiments) ? selectedCourse.experiments : []),
    [selectedCourse]
  );

  const selectedCourseExperimentIds = useMemo(
    () => selectedCourseExperiments.map((item) => String(item?.id || '').trim()).filter(Boolean),
    [selectedCourseExperiments]
  );

  const selectedCourseExperimentIdSet = useMemo(
    () => new Set(selectedCourseExperimentIds),
    [selectedCourseExperimentIds]
  );

  const filteredCourseProgress = useMemo(
    () => (Array.isArray(progress) ? progress : []).filter((item) => selectedCourseExperimentIdSet.has(String(item?.experiment_id || '').trim())),
    [progress, selectedCourseExperimentIdSet]
  );

  const filteredCourseSubmissions = useMemo(
    () => (Array.isArray(submissions) ? submissions : []).filter((item) => selectedCourseExperimentIdSet.has(String(item?.experiment_id || '').trim())),
    [submissions, selectedCourseExperimentIdSet]
  );

  const loadCourseSubmissions = useCallback(async () => {
    if (typeof onLoadSubmissions !== 'function') return;
    await onLoadSubmissions(selectedCourseExperimentIds);
  }, [onLoadSubmissions, selectedCourseExperimentIds]);

  const loadStatisticsStudents = useCallback(async () => {
    const courseId = String(selectedCourse?.id || '').trim();
    if (!courseId || !username) {
      setStatisticsStudents([]);
      return;
    }

    setLoadingStatisticsStudents(true);
    try {
      const pageSize = 100;
      let page = 1;
      let total = 0;
      const rows = [];
      const seen = new Set();

      do {
        const res = await axios.get(
          `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students`,
          {
            params: {
              teacher_username: username,
              page,
              page_size: pageSize,
            },
          }
        );
        const payload = res?.data || {};
        const items = Array.isArray(payload?.items) ? payload.items : [];
        total = Number(payload?.total || 0);

        items.forEach((item) => {
          const studentId = String(item?.student_id || '').trim();
          if (!studentId) return;
          const key = studentId.toLowerCase();
          if (seen.has(key)) return;
          seen.add(key);
          rows.push({
            student_id: studentId,
            real_name: String(item?.real_name || '').trim(),
            class_name: String(item?.class_name || '').trim(),
          });
        });

        if (items.length === 0) break;
        page += 1;
      } while (rows.length < total);

      setStatisticsStudents(rows);
    } catch (error) {
      console.error('loadStatisticsStudents failed', error);
      setStatisticsStudents([]);
    } finally {
      setLoadingStatisticsStudents(false);
    }
  }, [selectedCourse?.id, username]);

  const handleGradeSubmission = useCallback(async (submissionId, score, comment) => {
    if (typeof onGradeSubmission !== 'function') return;
    await onGradeSubmission(submissionId, score, comment);
    await loadCourseSubmissions();
  }, [onGradeSubmission, loadCourseSubmissions]);

  useEffect(() => {
    if (!Array.isArray(courses) || courses.length === 0) {
      if (viewMode === 'detail') setViewMode('home');
      if (selectedCourseId) setSelectedCourseId('');
      return;
    }

    if (viewMode === 'detail' && !selectedCourseId) {
      setSelectedCourseId(String(courses[0]?.id || ''));
      return;
    }

    const exists = courses.some((item) => String(item?.id || '').trim() === String(selectedCourseId || '').trim());
    if (viewMode === 'detail' && selectedCourseId && !exists) {
      setSelectedCourseId(String(courses[0]?.id || ''));
    }
  }, [courses, selectedCourseId, viewMode]);

  const filteredHomeCourses = useMemo(() => {
    const needle = String(homeKeyword || '').trim().toLowerCase();
    if (!needle) return courses || [];
    return (courses || []).filter((item) => {
      const name = String(item?.name || '').toLowerCase();
      const desc = String(item?.description || '').toLowerCase();
      return name.includes(needle) || desc.includes(needle);
    });
  }, [courses, homeKeyword]);

  const handleDeleteCourseFromHome = useCallback(async () => {
    if (typeof onDeleteCourse !== 'function') return;
    if (!Array.isArray(filteredHomeCourses) || filteredHomeCourses.length === 0) {
      alert('\u6682\u65e0\u53ef\u5220\u9664\u7684\u8bfe\u7a0b');
      return;
    }
    if (filteredHomeCourses.length > 1) {
      const keyword = String(homeKeyword || '').trim();
      if (!keyword) {
        alert('\u8bf7\u5148\u5728\u641c\u7d22\u6846\u8f93\u5165\u8bfe\u7a0b\u540d\uff0c\u5b9a\u4f4d\u5230\u552f\u4e00\u8bfe\u7a0b\u540e\u518d\u5220\u9664');
      } else {
        alert(`\u5f53\u524d\u641c\u7d22\u5339\u914d\u5230 ${filteredHomeCourses.length} \u95e8\u8bfe\u7a0b\uff0c\u8bf7\u7ee7\u7eed\u8f93\u5165\u66f4\u7cbe\u786e\u7684\u5173\u952e\u8bcd\u540e\u518d\u5220\u9664`);
      }
      return;
    }

    try {
      const deleted = await onDeleteCourse(filteredHomeCourses[0]);
      if (deleted) setHomeKeyword('');
    } catch (error) {
      console.error('delete course failed', error);
      alert(getErrorMessage(error, '\u5220\u9664\u8bfe\u7a0b\u5931\u8d25'));
    }
  }, [filteredHomeCourses, homeKeyword, onDeleteCourse]);

  const refreshCourseSummary = useCallback(() => {
    setSummaryRefreshTick((prev) => prev + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadAllOfferings = async () => {
      if (!username) {
        setAllOfferings([]);
        return;
      }
      try {
        const res = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
          params: { teacher_username: username },
        });
        if (cancelled) return;
        setAllOfferings(Array.isArray(res.data) ? res.data : []);
      } catch (error) {
        if (!cancelled) setAllOfferings([]);
      }
    };

    loadAllOfferings();
    return () => {
      cancelled = true;
    };
  }, [summaryRefreshTick, username]);

  useEffect(() => {
    setCoverSelectionMap(loadCoverSelectionMap());
  }, [viewMode]);

  const latestOfferingByCourseId = useMemo(() => {
    const mapping = {};
    (allOfferings || []).forEach((item) => {
      const courseId = String(item?.template_course_id || item?.course_id || '').trim();
      if (!courseId) return;
      const current = mapping[courseId];
      const currentTs = new Date(current?.updated_at || current?.created_at || 0).getTime();
      const candidateTs = new Date(item?.updated_at || item?.created_at || 0).getTime();
      if (!current || candidateTs >= currentTs) {
        mapping[courseId] = item;
      }
    });
    return mapping;
  }, [allOfferings]);

  const resolveCourseSystemCover = useCallback((course) => {
    const courseId = String(course?.id || '').trim();
    const offering = latestOfferingByCourseId[courseId];
    const offeringId = String(offering?.offering_id || '').trim();
    const selectedId = offeringId ? String(coverSelectionMap?.[offeringId] || '').trim() : '';
    const selectedCover = SYSTEM_COVERS.find((item) => item.id === selectedId);
    if (selectedCover) return selectedCover;
    const seed = String(offeringId || offering?.offering_code || courseId || 'system-cover-seed');
    const index = hashString(seed) % SYSTEM_COVERS.length;
    return SYSTEM_COVERS[index];
  }, [coverSelectionMap, latestOfferingByCourseId]);

  const renderCourseCover = useCallback((course) => {
    const cover = resolveCourseSystemCover(course);
    return (
      <div className="teacher-course-home-cover">
        <img src={cover.src} alt={cover.label} />
        <span>{'\u6559'}</span>
      </div>
    );
  }, [resolveCourseSystemCover]);

  useEffect(() => {
    setRecycleRows([]);
  }, [selectedCourseId]);

  useEffect(() => {
    setActiveManageTab('class-management');
  }, [selectedCourseId]);

  useEffect(() => {
    setStatisticsTab('overview');
    setStatisticsExperimentId('all');
    setStatisticsKeyword('');
    setStatisticsStudents([]);
  }, [selectedCourseId]);

  useEffect(() => {
    if (detailMenu !== 'management') return;
    if (activeManageTab === 'student-progress' && typeof onLoadProgress === 'function') {
      onLoadProgress();
      return;
    }
    if (activeManageTab === 'submission-review') {
      loadCourseSubmissions();
    }
  }, [activeManageTab, detailMenu, loadCourseSubmissions, onLoadProgress]);

  useEffect(() => {
    if (detailMenu !== 'statistics') return;
    loadCourseSubmissions();
    loadStatisticsStudents();
  }, [detailMenu, loadCourseSubmissions, loadStatisticsStudents]);

  const loadRecycleRows = useCallback(async () => {
    if (!selectedCourse?.id || typeof onListRecycleExperiments !== 'function') return;
    setLoadingRecycle(true);
    try {
      const rows = await onListRecycleExperiments(selectedCourse.id);
      setRecycleRows(Array.isArray(rows) ? rows : []);
    } catch (error) {
      console.error('load recycle failed', error);
      setRecycleRows([]);
      alert(getErrorMessage(error, '\u52a0\u8f7d\u56de\u6536\u7ad9\u5931\u8d25'));
    } finally {
      setLoadingRecycle(false);
    }
  }, [onListRecycleExperiments, selectedCourse?.id]);

  const openRecyclePage = useCallback(async () => {
    setDetailMenu('recycle');
    await loadRecycleRows();
  }, [loadRecycleRows]);

  useEffect(() => {
    if (detailMenu === 'recycle') {
      loadRecycleRows();
    }
  }, [detailMenu, loadRecycleRows]);

  const handleRestoreFromRecycle = useCallback(async (item) => {
    if (!item?.id || typeof onRestoreExperiment !== 'function') return;
    try {
      await onRestoreExperiment(item.id);
      await loadRecycleRows();
      alert('Assignment restored');
    } catch (error) {
      console.error('restore experiment failed', error);
      alert(getErrorMessage(error, '恢复作业失败'));
    }
  }, [onRestoreExperiment, loadRecycleRows]);

  const handlePermanentDeleteFromRecycle = useCallback(async (item) => {
    if (!item?.id || typeof onPermanentDeleteExperiment !== 'function') return;
    const targetTitle = String(item?.title || '\u8be5\u4f5c\u4e1a');
    if (!window.confirm(`\u786e\u5b9a\u5f7b\u5e95\u5220\u9664\u4f5c\u4e1a "${targetTitle}" \u5417\uff1f\u8be5\u64cd\u4f5c\u4e0d\u53ef\u6062\u590d\u3002`)) {
      return;
    }
    try {
      await onPermanentDeleteExperiment(item.id);
      await loadRecycleRows();
      alert('\u4f5c\u4e1a\u5df2\u5f7b\u5e95\u5220\u9664');
    } catch (error) {
      console.error('permanent delete experiment failed', error);
      alert(getErrorMessage(error, '\u5f7b\u5e95\u5220\u9664\u4f5c\u4e1a\u5931\u8d25'));
    }
  }, [onPermanentDeleteExperiment, loadRecycleRows]);

  const selectedCourseClassCount = useMemo(() => {
    const courseId = String(selectedCourse?.id || '').trim();
    if (!courseId) return 0;
    const classNames = new Set();

    (Array.isArray(allOfferings) ? allOfferings : []).forEach((item) => {
      const templateCourseId = String(item?.template_course_id || item?.course_id || '').trim();
      if (!templateCourseId || templateCourseId !== courseId) return;
      const status = String(item?.status || 'active').trim().toLowerCase();
      if (status === 'archived') return;
      const className = String(item?.class_name || '').trim();
      if (className) classNames.add(className);
    });

    (Array.isArray(selectedCourseClassNames) ? selectedCourseClassNames : []).forEach((name) => {
      const normalized = String(name || '').trim();
      if (normalized) classNames.add(normalized);
    });

    return classNames.size;
  }, [allOfferings, selectedCourse?.id, selectedCourseClassNames]);

  useEffect(() => {
    if (statisticsExperimentId === 'all') return;
    if (selectedCourseExperimentIdSet.has(statisticsExperimentId)) return;
    setStatisticsExperimentId('all');
  }, [selectedCourseExperimentIdSet, statisticsExperimentId]);

  useEffect(() => {
    let cancelled = false;
    const courseId = String(selectedCourse?.id || '').trim();

    if (!courseId || !username) {
      setSelectedCourseStudentCount(0);
      setSelectedCourseClassNames([]);
      return () => {
        cancelled = true;
      };
    }

    const loadCourseSummary = async () => {
      try {
        const [studentRes, classRes] = await Promise.allSettled([
          axios.get(
            `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students`,
            {
              params: {
                teacher_username: username,
                page: 1,
                page_size: 1,
              },
            }
          ),
          axios.get(
            `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(courseId)}/students/classes`,
            {
              params: { teacher_username: username },
            }
          ),
        ]);
        if (cancelled) return;
        if (studentRes.status === 'fulfilled') {
          setSelectedCourseStudentCount(Number(studentRes.value?.data?.total || 0));
        } else {
          setSelectedCourseStudentCount(0);
        }

        if (classRes.status === 'fulfilled') {
          const classNames = normalizeStringArray(
            (Array.isArray(classRes.value?.data) ? classRes.value.data : [])
              .map((item) => String(item?.value || item?.label || item?.name || '').trim())
          );
          setSelectedCourseClassNames(classNames);
        } else {
          setSelectedCourseClassNames([]);
        }
      } catch (error) {
        if (!cancelled) {
          setSelectedCourseStudentCount(0);
          setSelectedCourseClassNames([]);
        }
      }
    };

    loadCourseSummary();
    return () => {
      cancelled = true;
    };
  }, [selectedCourse?.id, summaryRefreshTick, username]);

  if (loading) return <div className="teacher-lab-loading">{"\u6b63\u5728\u52a0\u8f7d\u8bfe\u7a0b\u5e93..."}</div>;

  if (viewMode === 'home') {
    return (
      <div className="teacher-course-home">
        <div className="teacher-course-home-toolbar">
          <div className="teacher-course-home-actions">
            <button type="button" className="teacher-lab-create-btn" onClick={onCreateCourse}>{'+ \u65b0\u5efa\u8bfe\u7a0b'}</button>
            <button
              type="button"
              className="teacher-lab-delete-btn"
              onClick={handleDeleteCourseFromHome}
              disabled={!Array.isArray(courses) || courses.length === 0}
            >
              {'- \u5220\u9664\u8bfe\u7a0b'}
            </button>
          </div>
          <div className="teacher-course-search-box">
            <input
              type="text"
              value={homeKeyword}
              onChange={(event) => setHomeKeyword(event.target.value)}
              placeholder={"\u641c\u7d22"}
            />
          </div>
        </div>

        {filteredHomeCourses.length === 0 ? (
          <div className="teacher-lab-empty">{"\u6682\u65e0\u8bfe\u7a0b\uff0c\u8bf7\u5148\u521b\u5efa\u8bfe\u7a0b\u3002"}</div>
        ) : (
          <div className="teacher-course-home-grid">
            {filteredHomeCourses.map((course) => (
              <button
                key={course.id}
                type="button"
                className="teacher-course-home-card"
                onClick={() => {
                  setSelectedCourseId(String(course?.id || ''));
                  setDetailMenu('management');
                  setActiveManageTab('class-management');
                  setViewMode('detail');
                }}
              >
                {renderCourseCover(course)}
                <strong>{course?.name || '\u6211\u7684\u8bfe'}</strong>
                <span>{course?.created_by || username || '-'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (!selectedCourse) {
    return (
      <div className="teacher-lab-empty">
        {"\u672a\u627e\u5230\u8bfe\u7a0b\uff0c"}<button type="button" className="teacher-course-inline-btn" onClick={() => setViewMode('home')}>{"\u8fd4\u56de\u9996\u9875"}</button>
      </div>
    );
  }

  const sideMenus = [
    { key: 'management', label: '\u7ba1\u7406', enabled: true },
    { key: 'resources', label: '\u8d44\u6599', enabled: true },
    { key: 'assignments', label: '\u4f5c\u4e1a', enabled: true },
    { key: 'recycle', label: '\u56de\u6536\u7ad9', enabled: true },
    { key: 'statistics', label: '\u7edf\u8ba1', enabled: true },
  ];

  const renderResources = () => (
    <div className="teacher-course-pane">
      <ResourceFileManagement
        username={username}
        courseId={selectedCourse?.id || ''}
        countLabel={"\u8bfe\u7a0b\u8d44\u6599\u5171"}
      />
    </div>
  );

  const renderAssignments = () => (
    <div className="teacher-course-pane teacher-course-assignment-pane">
      <div className="teacher-course-pane-toolbar">
        <div className="teacher-course-home-actions">
          <button
            type="button"
            className="teacher-lab-create-btn"
            onClick={() => onCreateExperiment(selectedCourse)}
          >
            {'+ \u65b0\u5efa\u4f5c\u4e1a'}
          </button>
        </div>
        <div className="teacher-course-search-box">
          <input
            type="text"
            placeholder={"\u641c\u7d22"}
            value={assignmentKeyword}
            onChange={(event) => setAssignmentKeyword(event.target.value)}
          />
        </div>
      </div>
      {(() => {
        const rows = (Array.isArray(selectedCourse?.experiments) ? selectedCourse.experiments : [])
          .filter((item) => {
            const needle = String(assignmentKeyword || '').trim().toLowerCase();
            if (!needle) return true;
            const title = String(item?.title || '').toLowerCase();
            const desc = String(item?.description || '').toLowerCase();
            const tags = Array.isArray(item?.tags) ? item.tags.join(' ').toLowerCase() : '';
            return title.includes(needle) || desc.includes(needle) || tags.includes(needle);
          });

        if (rows.length === 0) {
          return <div className="teacher-course-empty-board">{"\u6682\u65e0\u4f5c\u4e1a"}</div>;
        }

        return (
          <div className="teacher-course-assignment-list">
            <div className="teacher-course-assignment-head">
              <span className="title">{"\u4f5c\u4e1a\u540d\u79f0"}</span>
              <span>{"\u72b6\u6001"}</span>
              <span>{"\u96be\u5ea6"}</span>
              <span>{"\u521b\u5efa\u65f6\u95f4"}</span>
              <span>{"\u64cd\u4f5c"}</span>
            </div>
            {rows.map((item) => (
              <div key={item?.id || item?.title} className="teacher-course-assignment-row">
                <div className="title">
                  <strong>{item?.title || '\u672a\u547d\u540d\u4f5c\u4e1a'}</strong>
                  <small>{item?.description || '\u6682\u65e0\u63cf\u8ff0'}</small>
                </div>
                <span>{item?.published ? '\u5df2\u53d1\u5e03' : '\u8349\u7a3f'}</span>
                <span>{item?.difficulty || '-'}</span>
                <span>{formatDateTime(item?.created_at)}</span>
                <span className="teacher-course-assignment-actions">
                  <button
                    type="button"
                    className="teacher-course-inline-btn"
                    onClick={() => onEditExperiment(selectedCourse, item)}
                  >
                    {'\u7f16\u8f91'}
                  </button>
                  <button
                    type="button"
                    className="teacher-course-inline-btn danger"
                    onClick={async () => {
                      try {
                        await onDeleteExperiment(selectedCourse, item);
                      } catch (error) {
                        console.error('delete experiment failed', error);
                        alert(getErrorMessage(error, '\u5220\u9664\u4f5c\u4e1a\u5931\u8d25'));
                      }
                    }}
                  >
                    {'\u5220\u9664'}
                  </button>
                </span>
              </div>
            ))}
          </div>
        );
      })()}
      <div className="teacher-course-recycle">
        <button type="button" className="teacher-course-recycle-link" onClick={openRecyclePage}>{"\u56de\u6536\u7ad9"}</button>
      </div>
    </div>
  );

  const renderRecycle = () => (
    <div className="teacher-course-pane teacher-course-assignment-pane">
      <div className="teacher-course-pane-toolbar">
        <div className="teacher-course-home-actions">
          <button type="button" className="teacher-course-outline-btn" onClick={() => setDetailMenu('assignments')}>
            {"\u8fd4\u56de\u4f5c\u4e1a"}
          </button>
        </div>
        <button
          type="button"
          className="teacher-course-plain-btn"
          onClick={() => loadRecycleRows()}
          disabled={loadingRecycle}
        >
          {"\u5237\u65b0"}
        </button>
      </div>

      <div className="teacher-course-recycle-panel">
        <div className="teacher-course-recycle-head">
          <strong>{"\u56de\u6536\u7ad9"}</strong>
          <span className="teacher-course-recycle-tip">{"\u5220\u9664\u540e\u7684\u4f5c\u4e1a\u572830\u5929\u5185\u53ef\u6062\u590d"}</span>
        </div>

        {loadingRecycle ? (
          <div className="teacher-course-recycle-empty">{"\u6b63\u5728\u52a0\u8f7d\u56de\u6536\u7ad9..."}</div>
        ) : recycleRows.length === 0 ? (
          <div className="teacher-course-recycle-empty">{"\u56de\u6536\u7ad9\u4e3a\u7a7a"}</div>
        ) : (
          <div className="teacher-course-assignment-list teacher-course-recycle-list">
            <div className="teacher-course-assignment-head">
              <span className="title">{"\u4f5c\u4e1a\u540d\u79f0"}</span>
              <span>{"\u5220\u9664\u65f6\u95f4"}</span>
              <span>{"\u8fc7\u671f\u65f6\u95f4"}</span>
              <span>{"\u72b6\u6001"}</span>
              <span>{"\u64cd\u4f5c"}</span>
            </div>
            {recycleRows.map((item) => (
              <div key={item?.id || item?.title} className="teacher-course-assignment-row">
                <div className="title">
                  <strong>{item?.title || '\u672a\u547d\u540d\u4f5c\u4e1a'}</strong>
                  <small>{item?.description || '\u6682\u65e0\u63cf\u8ff0'}</small>
                </div>
                <span>{formatDateTime(item?.deleted_at)}</span>
                <span>{formatDateTime(item?.expires_at)}</span>
                <span>{"\u53ef\u6062\u590d"}</span>
                <span className="teacher-course-assignment-actions">
                  <button
                    type="button"
                    className="teacher-course-inline-btn"
                    onClick={() => handleRestoreFromRecycle(item)}
                  >
                    {'\u6062\u590d'}
                  </button>
                  <button
                    type="button"
                    className="teacher-course-inline-btn danger"
                    onClick={() => handlePermanentDeleteFromRecycle(item)}
                  >
                    {'\u5f7b\u5e95\u5220\u9664'}
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
  const manageTabs = [
    { key: 'class-management', label: '\u73ed\u7ea7\u7ba1\u7406', enabled: true },
    { key: 'teacher-team', label: '\u6559\u5e08\u56e2\u961f\u7ba1\u7406', enabled: true },
    { key: 'student-progress', label: '\u5b66\u751f\u8fdb\u5ea6', enabled: true },
    { key: 'submission-review', label: '\u63d0\u4ea4\u5ba1\u9605', enabled: true },
    { key: 'course-management', label: '\u8bfe\u7a0b\u7ba1\u7406', enabled: true },
  ];

  const renderClassManagement = () => (
    <div className="teacher-course-manage-content">
      <TeacherUserManagement
        username={username}
        userRole={userRole}
        courseId={selectedCourse?.id || ''}
        onRosterChanged={refreshCourseSummary}
      />
    </div>
  );

  const renderCourseManagement = () => (
    <div className="teacher-course-manage-content">
      <OfferingDetail
        username={username}
        courseId={selectedCourse?.id || ''}
        courseName={selectedCourse?.name || ''}
        courseTeacher={selectedCourse?.created_by || username || ''}
        embedded
      />
    </div>
  );

  const renderTeacherTeamManagement = () => (
    <div className="teacher-course-manage-content">
      <TeacherTeamManagement username={username} courseId={selectedCourse?.id || ''} />
    </div>
  );

  const renderProgressManagement = () => (
    <div className="teacher-course-manage-content">
      <div className="teacher-course-manage-toolbar">
        <button type="button" className="teacher-course-plain-btn" onClick={() => typeof onLoadProgress === 'function' && onLoadProgress()}>
          {'\u5237\u65b0\u6570\u636e'}
        </button>
      </div>
      <ProgressPanel progress={filteredCourseProgress} loading={loadingProgress} courseMap={courseMap} />
    </div>
  );

  const renderReviewManagement = () => (
    <div className="teacher-course-manage-content">
      <div className="teacher-course-manage-toolbar">
        <button type="button" className="teacher-course-plain-btn" onClick={loadCourseSubmissions}>
          {'\u5237\u65b0\u6570\u636e'}
        </button>
      </div>
      <div className="teacher-lab-section">
        <TeacherReview
          username={username}
          submissions={filteredCourseSubmissions}
          loading={loadingSubmissions}
          onGrade={handleGradeSubmission}
        />
      </div>
    </div>
  );

  const renderManagement = () => (
    <div className="teacher-course-pane teacher-course-manage-pane">
      <div className="teacher-course-manage-tabs">
        {manageTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeManageTab === tab.key ? 'active' : ''}
            disabled={!tab.enabled}
            onClick={() => {
              if (!tab.enabled) return;
              setActiveManageTab(tab.key);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeManageTab === 'class-management' ? renderClassManagement() : null}
      {activeManageTab === 'teacher-team' ? renderTeacherTeamManagement() : null}
      {activeManageTab === 'student-progress' ? renderProgressManagement() : null}
      {activeManageTab === 'submission-review' ? renderReviewManagement() : null}
      {activeManageTab === 'course-management' ? renderCourseManagement() : null}
      {activeManageTab !== 'class-management' && activeManageTab !== 'teacher-team' && activeManageTab !== 'student-progress' && activeManageTab !== 'submission-review' && activeManageTab !== 'course-management' ? (
        <div className="teacher-course-empty-board">{'\u8be5\u529f\u80fd\u6b63\u5728\u5efa\u8bbe\u4e2d'}</div>
      ) : null}
    </div>
  );

  const renderStatistics = () => {
    const experimentOptions = [
      { id: 'all', title: '\u5168\u90e8\u4f5c\u4e1a' },
      ...selectedCourseExperiments.map((item) => ({
        id: String(item?.id || '').trim(),
        title: String(item?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a',
      })),
    ];

    const experimentMap = {};
    selectedCourseExperiments.forEach((item) => {
      const experimentId = String(item?.id || '').trim();
      if (!experimentId) return;
      experimentMap[experimentId] = {
        id: experimentId,
        title: String(item?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a',
      };
    });

    const keywordNeedle = String(statisticsKeyword || '').trim().toLowerCase();
    const visibleStudents = (Array.isArray(statisticsStudents) ? statisticsStudents : []).filter((student) => {
      if (!keywordNeedle) return true;
      const studentId = String(student?.student_id || '').toLowerCase();
      const realName = String(student?.real_name || '').toLowerCase();
      const className = String(student?.class_name || '').toLowerCase();
      return studentId.includes(keywordNeedle) || realName.includes(keywordNeedle) || className.includes(keywordNeedle);
    });

    const selectedExperiments = statisticsExperimentId === 'all'
      ? selectedCourseExperiments
      : selectedCourseExperiments.filter((item) => String(item?.id || '').trim() === statisticsExperimentId);
    const totalAssignmentCount = selectedExperiments.length;

    const submissionMap = new Map();
    (Array.isArray(filteredCourseSubmissions) ? filteredCourseSubmissions : []).forEach((item) => {
      const studentId = String(item?.student_id || '').trim();
      const experimentId = String(item?.experiment_id || '').trim();
      if (!studentId || !experimentId) return;
      const key = `${studentId}::${experimentId}`;
      const existing = submissionMap.get(key);
      if (!existing) {
        submissionMap.set(key, item);
        return;
      }
      const existingTs = new Date(existing?.submit_time || existing?.updated_at || existing?.created_at || 0).getTime();
      const candidateTs = new Date(item?.submit_time || item?.updated_at || item?.created_at || 0).getTime();
      if (candidateTs >= existingTs) submissionMap.set(key, item);
    });

    const buildSubmissionSnapshot = (submission) => {
      const statusKey = progressStatusKey(submission?.status);
      const scoreValue = toNumericScore(submission?.score);
      const hasSubmitted = Boolean(
        submission
          && (statusKey === 'submitted' || statusKey === 'graded' || submission?.submit_time)
      );
      const missing = !hasSubmitted || scoreValue === null;
      return {
        missing,
        scoreValue,
        scoreText: missing ? '\u7f3a\u4ea4' : formatScoreValue(scoreValue),
        statusText: missing ? '\u7f3a\u4ea4' : (statusKey === 'graded' ? '\u5df2\u8bc4\u5206' : '\u5df2\u63d0\u4ea4'),
        submitTimeText: missing ? '\u7f3a\u4ea4' : formatDateTime(submission?.submit_time),
      };
    };

    const aggregateRows = visibleStudents.map((student) => {
      const studentId = String(student?.student_id || '').trim();
      let scoreSum = 0;
      let submittedCount = 0;

      selectedExperiments.forEach((experiment) => {
        const experimentId = String(experiment?.id || '').trim();
        const submission = submissionMap.get(`${studentId}::${experimentId}`);
        const snapshot = buildSubmissionSnapshot(submission);
        if (snapshot.missing) return;
        submittedCount += 1;
        scoreSum += snapshot.scoreValue || 0;
      });

      const missingCount = Math.max(totalAssignmentCount - submittedCount, 0);
      const averageScore = submittedCount > 0 ? (scoreSum / submittedCount) : null;
      return {
        student_id: studentId || '-',
        real_name: String(student?.real_name || '').trim() || '-',
        class_name: String(student?.class_name || '').trim() || '-',
        submitted_count: submittedCount,
        missing_count: missingCount,
        average_score: averageScore,
      };
    });

    const singleAssignment = statisticsExperimentId === 'all' ? null : experimentMap[statisticsExperimentId];
    const singleRows = singleAssignment ? visibleStudents.map((student) => {
      const studentId = String(student?.student_id || '').trim();
      const submission = submissionMap.get(`${studentId}::${singleAssignment.id}`);
      const snapshot = buildSubmissionSnapshot(submission);
      return {
        student_id: studentId || '-',
        real_name: String(student?.real_name || '').trim() || '-',
        class_name: String(student?.class_name || '').trim() || '-',
        assignment_name: singleAssignment.title,
        ...snapshot,
      };
    }) : [];

    const summary = (() => {
      const scoreValues = statisticsExperimentId === 'all'
        ? aggregateRows.map((item) => toNumericScore(item.average_score)).filter((item) => item !== null)
        : singleRows.map((item) => toNumericScore(item.scoreValue)).filter((item) => item !== null);
      const expectedCount = statisticsExperimentId === 'all'
        ? visibleStudents.length * totalAssignmentCount
        : singleRows.length;
      const submittedCount = statisticsExperimentId === 'all'
        ? aggregateRows.reduce((acc, item) => acc + item.submitted_count, 0)
        : singleRows.filter((item) => !item.missing).length;
      const missingStudentCount = statisticsExperimentId === 'all'
        ? aggregateRows.filter((item) => item.missing_count > 0).length
        : singleRows.filter((item) => item.missing).length;
      const averageScore = scoreValues.length > 0
        ? (scoreValues.reduce((acc, item) => acc + item, 0) / scoreValues.length)
        : null;
      const maxScore = scoreValues.length > 0 ? Math.max(...scoreValues) : null;
      const minScore = scoreValues.length > 0 ? Math.min(...scoreValues) : null;
      const submissionRate = expectedCount > 0 ? ((submittedCount / expectedCount) * 100) : 0;
      return {
        averageScore,
        maxScore,
        minScore,
        submissionRate,
        missingStudentCount,
      };
    })();

    const exportRows = [];
    if (totalAssignmentCount > 0) {
      visibleStudents.forEach((student) => {
        const studentId = String(student?.student_id || '').trim();
        selectedExperiments.forEach((experiment) => {
          const experimentId = String(experiment?.id || '').trim();
          const assignmentName = String(experiment?.title || '').trim() || '\u672a\u547d\u540d\u4f5c\u4e1a';
          const submission = submissionMap.get(`${studentId}::${experimentId}`);
          const snapshot = buildSubmissionSnapshot(submission);
          exportRows.push({
            '\u5b66\u53f7': studentId || '-',
            '\u59d3\u540d': String(student?.real_name || '').trim() || '-',
            '\u73ed\u7ea7': String(student?.class_name || '').trim() || '-',
            '\u4f5c\u4e1a\u540d\u79f0': assignmentName,
            '\u6210\u7ee9': snapshot.scoreText,
            '\u63d0\u4ea4\u72b6\u6001': snapshot.statusText,
            '\u63d0\u4ea4\u65f6\u95f4': snapshot.submitTimeText,
          });
        });
      });
    }

    const handleExportScores = () => {
      if (exportRows.length === 0) {
        alert('\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u53ef\u5bfc\u51fa\u6210\u7ee9');
        return;
      }
      const headers = ['\u5b66\u53f7', '\u59d3\u540d', '\u73ed\u7ea7', '\u4f5c\u4e1a\u540d\u79f0', '\u6210\u7ee9', '\u63d0\u4ea4\u72b6\u6001', '\u63d0\u4ea4\u65f6\u95f4'];
      const lines = [
        headers.map((item) => csvEscape(item)).join(','),
        ...exportRows.map((row) => headers.map((field) => csvEscape(row[field])).join(',')),
      ];
      const csv = lines.join('\r\n');
      const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const courseName = String(selectedCourse?.name || 'course').trim() || 'course';
      const selectedAssignmentName = statisticsExperimentId === 'all'
        ? 'all-assignments'
        : (experimentMap[statisticsExperimentId]?.title || 'assignment');
      const safeCourseName = courseName.replace(/[\\/:*?"<>|]/g, '_');
      const safeAssignmentName = String(selectedAssignmentName).replace(/[\\/:*?"<>|]/g, '_');
      link.href = url;
      link.download = `${safeCourseName}-${safeAssignmentName}-scores.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    };

    return (
      <div className="teacher-course-stat-layout">
        <div className="teacher-course-stat-top">
          <div className="teacher-course-stat-main">
            <h2>{selectedCourse?.name || '\u6211\u7684\u8bfe'}</h2>
            <p>{`\u8bfe\u7a0b\u6559\u5e08\uff1a${selectedCourse?.created_by || username || '-'}`}</p>
          </div>
          <div className="teacher-course-stat-metrics">
            <div><span>{'\u73ed\u7ea7\u6570'}</span><strong>{selectedCourseClassCount}</strong><em>{'\u4e2a'}</em></div>
            <div><span>{'\u9009\u8bfe\u5b66\u751f\u6570'}</span><strong>{selectedCourseStudentCount}</strong><em>{'\u4eba'}</em></div>
          </div>
        </div>

        <div className="teacher-course-stat-tabs">
          <button
            type="button"
            className={statisticsTab === 'overview' ? 'active' : ''}
            onClick={() => setStatisticsTab('overview')}
          >
            {'\u57fa\u7840\u6570\u636e'}
          </button>
          <button
            type="button"
            className={statisticsTab === 'scores' ? 'active' : ''}
            onClick={() => setStatisticsTab('scores')}
          >
            {'\u5b66\u751f\u6210\u7ee9'}
          </button>
        </div>

        <div className="teacher-course-stat-grid">
          {statisticsTab === 'overview' ? (
            <section className="teacher-course-stat-card">
              <h3>{'\u5b66\u60c5\u6982\u89c8'}</h3>
              <div className="teacher-course-stat-band">
                <div><span>{'\u8fd1\u4e00\u4e2a\u6708\u6d3b\u8dc3\u5b66\u751f\u6570'}</span><strong>0</strong><em>{'\u4eba'}</em></div>
                <div><span>{'\u8fd1\u4e00\u4e2a\u6708\u5e08\u751f\u6d3b\u52a8\u6570'}</span><strong>0</strong><em>{'\u6b21'}</em></div>
                <div><span>{'\u8fd1\u4e00\u4e2a\u6708\u6d3b\u8dc3\u73ed\u7ea7\u6570'}</span><strong>0</strong><em>{'\u4e2a'}</em></div>
              </div>
              <div className="teacher-course-heatmap-placeholder"><strong>{'\u8fd17\u65e5\u5b66\u751f\u5728\u7ebf\u5b66\u4e60\u70ed\u529b\u56fe'}</strong></div>
            </section>
          ) : (
            <section className="teacher-course-stat-card">
              <h3>{'\u5b66\u751f\u6210\u7ee9'}</h3>
              <div className="teacher-course-score-toolbar">
                <div className="teacher-course-score-controls">
                  <label htmlFor="teacher-score-assignment-filter">{'\u4f5c\u4e1a'}</label>
                  <select
                    id="teacher-score-assignment-filter"
                    value={statisticsExperimentId}
                    onChange={(event) => setStatisticsExperimentId(event.target.value)}
                  >
                    {experimentOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </div>
                <div className="teacher-course-score-controls grow">
                  <label htmlFor="teacher-score-search">{'\u641c\u7d22'}</label>
                  <input
                    id="teacher-score-search"
                    type="text"
                    value={statisticsKeyword}
                    onChange={(event) => setStatisticsKeyword(event.target.value)}
                    placeholder={'\u8bf7\u8f93\u5165\u5b66\u53f7/\u59d3\u540d/\u73ed\u7ea7'}
                  />
                </div>
                <button
                  type="button"
                  className="teacher-lab-create-btn"
                  onClick={handleExportScores}
                  disabled={loadingSubmissions || loadingStatisticsStudents || exportRows.length === 0}
                >
                  {'\u5bfc\u51fa\u6210\u7ee9'}
                </button>
              </div>

              <div className="teacher-course-score-band">
                <div><span>{'\u5e73\u5747\u5206'}</span><strong>{summary.averageScore === null ? '--' : formatScoreValue(summary.averageScore)}</strong></div>
                <div><span>{'\u6700\u9ad8\u5206'}</span><strong>{summary.maxScore === null ? '--' : formatScoreValue(summary.maxScore)}</strong></div>
                <div><span>{'\u6700\u4f4e\u5206'}</span><strong>{summary.minScore === null ? '--' : formatScoreValue(summary.minScore)}</strong></div>
                <div><span>{'\u63d0\u4ea4\u7387'}</span><strong>{`${summary.submissionRate.toFixed(1)}%`}</strong></div>
                <div><span>{'\u7f3a\u4ea4\u4eba\u6570'}</span><strong>{summary.missingStudentCount}</strong></div>
              </div>

              {loadingSubmissions || loadingStatisticsStudents ? (
                <div className="teacher-course-score-empty">{'\u6b63\u5728\u52a0\u8f7d\u6210\u7ee9\u6570\u636e...'}</div>
              ) : totalAssignmentCount === 0 ? (
                <div className="teacher-course-score-empty">{'\u5f53\u524d\u8bfe\u7a0b\u6682\u65e0\u4f5c\u4e1a'}</div>
              ) : (
                <div className="teacher-lab-table-wrap">
                  <table className="teacher-lab-table teacher-course-score-table">
                    <thead>
                      {statisticsExperimentId === 'all' ? (
                        <tr>
                          <th>{'\u5b66\u53f7'}</th>
                          <th>{'\u59d3\u540d'}</th>
                          <th>{'\u73ed\u7ea7'}</th>
                          <th>{'\u5e73\u5747\u5206'}</th>
                          <th>{'\u5df2\u4ea4\u4f5c\u4e1a\u6570'}</th>
                          <th>{'\u7f3a\u4ea4\u4f5c\u4e1a\u6570'}</th>
                        </tr>
                      ) : (
                        <tr>
                          <th>{'\u5b66\u53f7'}</th>
                          <th>{'\u59d3\u540d'}</th>
                          <th>{'\u73ed\u7ea7'}</th>
                          <th>{'\u4f5c\u4e1a\u540d\u79f0'}</th>
                          <th>{'\u6210\u7ee9'}</th>
                          <th>{'\u63d0\u4ea4\u72b6\u6001'}</th>
                          <th>{'\u63d0\u4ea4\u65f6\u95f4'}</th>
                        </tr>
                      )}
                    </thead>
                    <tbody>
                      {statisticsExperimentId === 'all' ? (
                        aggregateRows.length === 0 ? (
                          <tr>
                            <td colSpan="6" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
                          </tr>
                        ) : (
                          aggregateRows.map((row) => (
                            <tr key={`${row.student_id}-aggregate`}>
                              <td>{row.student_id}</td>
                              <td>{row.real_name}</td>
                              <td>{row.class_name}</td>
                              <td>
                                {row.average_score === null ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : formatScoreValue(row.average_score)}
                              </td>
                              <td>{row.submitted_count}</td>
                              <td>
                                {row.missing_count > 0 ? (
                                  <span className="teacher-course-missing-text">{row.missing_count}</span>
                                ) : row.missing_count}
                              </td>
                            </tr>
                          ))
                        )
                      ) : (
                        singleRows.length === 0 ? (
                          <tr>
                            <td colSpan="7" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
                          </tr>
                        ) : (
                          singleRows.map((row) => (
                            <tr key={`${row.student_id}-${row.assignment_name}`}>
                              <td>{row.student_id}</td>
                              <td>{row.real_name}</td>
                              <td>{row.class_name}</td>
                              <td>{row.assignment_name}</td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.scoreText}
                              </td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.statusText}
                              </td>
                              <td>
                                {row.missing ? (
                                  <span className="teacher-course-missing-text">{'\u7f3a\u4ea4'}</span>
                                ) : row.submitTimeText}
                              </td>
                            </tr>
                          ))
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    );
  };

  const renderContent = () => {
    if (detailMenu === 'resources') return renderResources();
    if (detailMenu === 'assignments') return renderAssignments();
    if (detailMenu === 'recycle') return renderRecycle();
    if (detailMenu === 'management') return renderManagement();
    if (detailMenu === 'statistics') return renderStatistics();
    return renderResources();
  };

  return (
    <div className="teacher-course-detail-shell">
      <aside className="teacher-course-detail-sidebar">
        <button type="button" className="teacher-course-detail-cover" onClick={() => setViewMode('home')}>
          {renderCourseCover(selectedCourse)}
          <div className="teacher-course-detail-cover-links"><span>{'\u8bfe\u7a0b\u95e8\u6237'}</span><span>{'\u94fe\u63a5'}</span></div>
        </button>
        <div className="teacher-course-detail-title">{selectedCourse?.name || '\u6211\u7684\u8bfe'}</div>

        <div className="teacher-course-detail-menu">
          {sideMenus.map((item) => (
            <button
              key={item.key}
              type="button"
              className={detailMenu === item.key ? 'active' : ''}
              disabled={!item.enabled}
              onClick={() => item.enabled && setDetailMenu(item.key)}
            >
              <span className="dot" />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="teacher-course-detail-main">
        {renderContent()}
      </main>
    </div>
  );
}
function ProgressPanel({ progress, loading, courseMap }) {
  const [filter, setFilter] = useState('all');
  const total = progress.length;
  const completed = useMemo(() => progress.filter((item) => isCompleted(item.status)).length, [progress]);
  const pending = total - completed;
  const rate = total > 0 ? ((completed / total) * 100).toFixed(1) : '0.0';

  const rows = useMemo(() => {
    if (filter === 'completed') return progress.filter((item) => isCompleted(item.status));
    if (filter === 'incomplete') return progress.filter((item) => !isCompleted(item.status));
    return progress;
  }, [filter, progress]);

  const statusLabel = {
    'not-started': '\u672a\u5f00\u59cb',
    'in-progress': '\u8fdb\u884c\u4e2d',
    submitted: '\u5df2\u63d0\u4ea4',
    graded: '\u5df2\u8bc4\u5206',
  };

  if (loading) return <div className="teacher-lab-loading">{'\u6b63\u5728\u52a0\u8f7d\u5b66\u751f\u8fdb\u5ea6...'}</div>;

  return (
    <div className="teacher-lab-section teacher-lab-progress">
      <div className="teacher-lab-progress-stats">
        <div className="teacher-lab-progress-stat"><span>{'\u603b\u4efb\u52a1'}</span><strong>{total}</strong></div>
        <div className="teacher-lab-progress-stat success"><span>{'\u5df2\u5b8c\u6210'}</span><strong>{completed}</strong></div>
        <div className="teacher-lab-progress-stat warning"><span>{'\u672a\u5b8c\u6210'}</span><strong>{pending}</strong></div>
        <div className="teacher-lab-progress-stat info"><span>{'\u5b8c\u6210\u7387'}</span><strong>{rate}%</strong></div>
      </div>

      <div className="teacher-lab-filter-row">
        <label htmlFor="teacher-progress-filter">{'\u72b6\u6001\u7b5b\u9009\uff1a'}</label>
        <select id="teacher-progress-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="all">{'\u5168\u90e8'}</option>
          <option value="completed">{'\u5df2\u5b8c\u6210'}</option>
          <option value="incomplete">{'\u672a\u5b8c\u6210'}</option>
        </select>
      </div>

      <div className="teacher-lab-table-wrap">
        <table className="teacher-lab-table">
          <thead>
            <tr>
              <th>{'\u7528\u6237\u6807\u8bc6'}</th>
              <th>{'\u5b9e\u9a8c\u6807\u9898'}</th>
              <th>{'\u72b6\u6001'}</th>
              <th>{'\u5f00\u59cb\u65f6\u95f4'}</th>
              <th>{'\u63d0\u4ea4\u65f6\u95f4'}</th>
              <th>{'\u8bc4\u5206'}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan="6" className="teacher-lab-empty-row">{'\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6682\u65e0\u6570\u636e'}</td>
              </tr>
            ) : (
              rows.map((item, index) => {
                const key = progressStatusKey(item.status);
                return (
                  <tr key={`${item.student_id}-${item.experiment_id}-${index}`}>
                    <td>{item.student_id || '-'}</td>
                    <td>{courseMap[item.experiment_id]?.title || item.experiment_id || '-'}</td>
                    <td><span className={`teacher-lab-progress-badge ${key}`}>{statusLabel[key] || item.status || '-'}</span></td>
                    <td>{formatDateTime(item.start_time)}</td>
                    <td>{formatDateTime(item.submit_time)}</td>
                    <td>{item.score === null || item.score === undefined ? '-' : item.score}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
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
      alert(getErrorMessage(error, '保存密保问题失败'));
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
function CourseEditorModal({ initialCourse, onClose, onCreate, onUpdate }) {
  const isEdit = Boolean(initialCourse);
  const [formData, setFormData] = useState(() => ({
    name: initialCourse?.name || '',
    description: initialCourse?.description || '',
  }));
  const [saving, setSaving] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      if (isEdit) {
        await onUpdate(initialCourse, formData);
        alert('\u8bfe\u7a0b\u66f4\u65b0\u6210\u529f');
      } else {
        await onCreate(formData);
        alert('\u8bfe\u7a0b\u521b\u5efa\u6210\u529f');
      }
      onClose();
    } catch (error) {
      console.error('save course failed', error);
      alert(getErrorMessage(error, isEdit ? '\u66f4\u65b0\u8bfe\u7a0b\u5931\u8d25' : '\u521b\u5efa\u8bfe\u7a0b\u5931\u8d25'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <h2>{isEdit ? '\u7f16\u8f91\u8bfe\u7a0b' : '\u65b0\u5efa\u8bfe\u7a0b'}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label htmlFor="course-name">{'\u8bfe\u7a0b\u540d\u79f0'}</label>
            <input
              id="course-name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u8bfe\u7a0b\u540d\u79f0'}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="course-description">{'\u8bfe\u7a0b\u7b80\u4ecb'}</label>
            <textarea
              id="course-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u8bfe\u7a0b\u7b80\u4ecb\uff08\u53ef\u9009\uff09'}
            />
          </div>
          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={saving}>{'\u53d6\u6d88'}</button>
            <button type="submit" disabled={saving}>
              {saving ? '\u4fdd\u5b58\u4e2d...' : (isEdit ? '\u4fdd\u5b58\u4fee\u6539' : '\u521b\u5efa\u8bfe\u7a0b')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ExperimentEditorModal({ username, course, initialExperiment, onClose, onCreate, onUpdate }) {
  const isEdit = Boolean(initialExperiment);
  const [formData, setFormData] = useState(() => ({
    title: initialExperiment?.title || '',
    description: initialExperiment?.description || '',
    difficulty: initialExperiment?.difficulty || '\u4e2d\u7ea7',
    tags: Array.isArray(initialExperiment?.tags) ? initialExperiment.tags.join(', ') : '',
    notebook_path: initialExperiment?.notebook_path || '',
    published: initialExperiment ? Boolean(initialExperiment?.published) : true,
    publish_scope: normalizePublishScope(initialExperiment?.publish_scope),
    target_class_names: normalizeStringArray(initialExperiment?.target_class_names),
    target_student_ids: normalizeStringArray(initialExperiment?.target_student_ids),
  }));
  const [targets, setTargets] = useState({ classes: [], students: [] });
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [studentKeyword, setStudentKeyword] = useState('');
  const [files, setFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const normalizedCourseId = String(course?.id || '').trim();

  useEffect(() => {
    let cancelled = false;
    const loadTargets = async () => {
      if (!username || !normalizedCourseId) {
        setTargets({ classes: [], students: [] });
        return;
      }
      setLoadingTargets(true);
      try {
        const loadCourseStudents = async () => {
          const pageSize = 100;
          let page = 1;
          let total = 0;
          const students = [];
          const seen = new Set();

          do {
            const res = await axios.get(
              `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(normalizedCourseId)}/students`,
              {
                params: {
                  teacher_username: username,
                  page,
                  page_size: pageSize,
                },
              }
            );
            const payload = res.data || {};
            const items = Array.isArray(payload?.items) ? payload.items : [];
            total = Number(payload?.total || 0);

            items.forEach((item) => {
              const studentId = String(item?.student_id || '').trim();
              if (!studentId) return;
              const key = studentId.toLowerCase();
              if (seen.has(key)) return;
              seen.add(key);
              students.push({
                student_id: studentId,
                real_name: String(item?.real_name || '').trim(),
                class_name: String(item?.class_name || '').trim(),
              });
            });

            if (items.length === 0) break;
            page += 1;
          } while (students.length < total);

          return students;
        };

        const [classRes, students] = await Promise.all([
          axios.get(`${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(normalizedCourseId)}/students/classes`, {
            params: { teacher_username: username },
          }),
          loadCourseStudents(),
        ]);

        const classNames = normalizeStringArray(
          (Array.isArray(classRes.data) ? classRes.data : []).map((item) => String(item?.label || item?.value || '').trim())
        );
        if (cancelled) return;
        setTargets({
          classes: classNames.map((name) => ({ id: name, name })),
          students,
        });
      } catch (error) {
        if (!cancelled) setTargets({ classes: [], students: [] });
      } finally {
        if (!cancelled) setLoadingTargets(false);
      }
    };

    loadTargets();
    return () => {
      cancelled = true;
    };
  }, [normalizedCourseId, username]);

  const classes = Array.isArray(targets?.classes) ? targets.classes : [];
  const filteredStudents = useMemo(() => {
    const students = Array.isArray(targets?.students) ? targets.students : [];
    const needle = String(studentKeyword || '').trim().toLowerCase();
    if (!needle) return students;
    return students.filter((item) => {
      const sid = String(item?.student_id || '').toLowerCase();
      const realName = String(item?.real_name || '').toLowerCase();
      const className = String(item?.class_name || '').toLowerCase();
      return sid.includes(needle) || realName.includes(needle) || className.includes(needle);
    });
  }, [targets?.students, studentKeyword]);

  const onFileChange = (event) => {
    const next = Array.from(event.target.files || []);
    setFiles((prev) => {
      const keys = new Set(prev.map((file) => `${file.name}-${file.size}`));
      return [...prev, ...next.filter((file) => !keys.has(`${file.name}-${file.size}`))];
    });
    event.target.value = '';
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const toggleClass = (name) => {
    const normalizedName = String(name || '').trim();
    if (!normalizedName) return;
    setFormData((prev) => ({
      ...prev,
      target_class_names: prev.target_class_names.includes(normalizedName)
        ? prev.target_class_names.filter((item) => item !== normalizedName)
        : [...prev.target_class_names, normalizedName],
    }));
  };

  const toggleStudent = (studentId) => {
    const normalizedStudentId = String(studentId || '').trim();
    if (!normalizedStudentId) return;
    setFormData((prev) => ({
      ...prev,
      target_student_ids: prev.target_student_ids.includes(normalizedStudentId)
        ? prev.target_student_ids.filter((item) => item !== normalizedStudentId)
        : [...prev.target_student_ids, normalizedStudentId],
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;

    if (formData.published && formData.publish_scope === 'class' && formData.target_class_names.length === 0) {
      alert('\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u73ed\u7ea7');
      return;
    }
    if (formData.published && formData.publish_scope === 'student' && formData.target_student_ids.length === 0) {
      alert('\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u5b66\u751f');
      return;
    }

    setSaving(true);
    try {
      const experiment = isEdit
        ? await onUpdate(course, initialExperiment, formData)
        : await onCreate(course, formData);

      let uploadError = null;
      if (experiment?.id && files.length > 0) {
        try {
          const data = new FormData();
          files.forEach((file) => data.append('files', file));
          await axios.post(`${API_BASE_URL}/api/teacher/experiments/${experiment.id}/attachments`, data, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
        } catch (error) {
          uploadError = error;
        }
      }

      if (uploadError) {
        alert(`\u5b9e\u9a8c\u5df2\u4fdd\u5b58\uff0c\u4f46\u9644\u4ef6\u4e0a\u4f20\u5931\u8d25\uff1a${getErrorMessage(uploadError, '\u8bf7\u7a0d\u540e\u91cd\u8bd5')}`);
        onClose();
        return;
      }

      alert(isEdit ? '\u5b9e\u9a8c\u66f4\u65b0\u6210\u529f' : '\u5b9e\u9a8c\u521b\u5efa\u6210\u529f');
      onClose();
    } catch (error) {
      console.error('save experiment failed', error);
      alert(getErrorMessage(error, isEdit ? '\u66f4\u65b0\u5b9e\u9a8c\u5931\u8d25' : '\u521b\u5efa\u5b9e\u9a8c\u5931\u8d25'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <h2>{isEdit ? '\u7f16\u8f91\u5b9e\u9a8c' : `\u65b0\u5efa\u5b9e\u9a8c\uff1a${course?.name || ''}`}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label htmlFor="experiment-course-name">{'\u6240\u5c5e\u8bfe\u7a0b'}</label>
            <input id="experiment-course-name" type="text" value={course?.name || ''} disabled />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-title">{'\u5b9e\u9a8c\u6807\u9898'}</label>
            <input
              id="experiment-title"
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u5b9e\u9a8c\u6807\u9898'}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-description">{'\u5b9e\u9a8c\u63cf\u8ff0'}</label>
            <textarea
              id="experiment-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u5b9e\u9a8c\u63cf\u8ff0'}
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-difficulty">{'\u96be\u5ea6'}</label>
            <select
              id="experiment-difficulty"
              value={formData.difficulty}
              onChange={(e) => setFormData({ ...formData, difficulty: e.target.value })}
            >
              <option value={'\u521d\u7ea7'}>{'\u521d\u7ea7'}</option>
              <option value={'\u4e2d\u7ea7'}>{'\u4e2d\u7ea7'}</option>
              <option value={'\u9ad8\u7ea7'}>{'\u9ad8\u7ea7'}</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="experiment-tags">{'\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff09'}</label>
            <input
              id="experiment-tags"
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              placeholder={'\u4f8b\u5982\uff1aPython\uff0c\u5faa\u73af\uff0c\u5217\u8868'}
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-notebook">{'Notebook \u8def\u5f84'}</label>
            <input id="experiment-notebook" type="text" value={formData.notebook_path} onChange={(e) => setFormData({ ...formData, notebook_path: e.target.value })} placeholder="course/example.ipynb" />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-attachments">{'\u4e0a\u4f20\u9644\u4ef6\uff08\u53ef\u591a\u9009\uff09'}</label>
            <input id="experiment-attachments" type="file" multiple onChange={onFileChange} />
            {files.length > 0 ? (
              <ul className="teacher-lab-upload-list">
                {files.map((file, index) => (
                  <li key={`${file.name}-${file.size}`}>
                    <span>{file.name}</span>
                    <button type="button" onClick={() => removeFile(index)}>{'\u5220\u9664'}</button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="form-group checkbox">
            <label htmlFor="experiment-published">
              <input id="experiment-published" type="checkbox" checked={formData.published} onChange={(e) => setFormData({ ...formData, published: e.target.checked })} />
              {'\u7acb\u5373\u53d1\u5e03\u7ed9\u5b66\u751f'}
            </label>
          </div>

          {formData.published ? (
            <>
              <div className="form-group">
                <label>{'\u53d1\u5e03\u8303\u56f4'}</label>
                <div className="publish-scope-row">
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'all'} onChange={() => setFormData({ ...formData, publish_scope: 'all', target_class_names: [], target_student_ids: [] })} /> {'\u5168\u90e8\u5b66\u751f'}</label>
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'class'} onChange={() => setFormData({ ...formData, publish_scope: 'class', target_student_ids: [] })} /> {'\u6307\u5b9a\u73ed\u7ea7'}</label>
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'student'} onChange={() => setFormData({ ...formData, publish_scope: 'student', target_class_names: [] })} /> {'\u6307\u5b9a\u5b66\u751f'}</label>
                </div>
              </div>

              {formData.publish_scope === 'class' ? (
                <div className="form-group">
                  <label>{`\u9009\u62e9\u73ed\u7ea7\uff08\u5df2\u9009 ${formData.target_class_names.length}\uff09`}</label>
                  {loadingTargets ? (
                    <div className="publish-target-loading">{'\u6b63\u5728\u52a0\u8f7d\u53ef\u9009\u73ed\u7ea7...'}</div>
                  ) : (
                    <div className="publish-target-list">
                      {classes.length === 0 ? (
                        <div className="publish-target-empty">{'\u6682\u65e0\u53ef\u9009\u73ed\u7ea7'}</div>
                      ) : (
                        classes.map((item) => {
                          const name = String(item?.name || '').trim();
                          return (
                            <label key={item?.id || name}>
                              <input type="checkbox" checked={formData.target_class_names.includes(name)} onChange={() => toggleClass(name)} />
                              <span>{name}</span>
                            </label>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              ) : null}

              {formData.publish_scope === 'student' ? (
                <div className="form-group">
                  <label>{`\u9009\u62e9\u5b66\u751f\uff08\u5df2\u9009 ${formData.target_student_ids.length}\uff09`}</label>
                  <input
                    type="text"
                    value={studentKeyword}
                    onChange={(event) => setStudentKeyword(event.target.value)}
                    placeholder={'\u8bf7\u8f93\u5165\u5b66\u53f7/\u59d3\u540d/\u73ed\u7ea7\u5173\u952e\u5b57'}
                  />
                  {loadingTargets ? (
                    <div className="publish-target-loading">{'\u6b63\u5728\u52a0\u8f7d\u53ef\u9009\u5b66\u751f...'}</div>
                  ) : (
                    <div className="publish-target-list">
                      {filteredStudents.length === 0 ? (
                        <div className="publish-target-empty">{'\u6682\u65e0\u53ef\u9009\u5b66\u751f'}</div>
                      ) : (
                        filteredStudents.map((item) => {
                          const studentId = String(item?.student_id || '').trim();
                          const realName = String(item?.real_name || '').trim();
                          const className = String(item?.class_name || '').trim();
                          return (
                            <label key={studentId}>
                              <input type="checkbox" checked={formData.target_student_ids.includes(studentId)} onChange={() => toggleStudent(studentId)} />
                              <span>{`${studentId}${realName ? ` \u00b7 ${realName}` : ''}${className ? ` \u00b7 ${className}` : ''}`}</span>
                            </label>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              ) : null}
            </>
          ) : null}

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={saving}>{'\u53d6\u6d88'}</button>
            <button type="submit" disabled={saving}>{saving ? '\u4fdd\u5b58\u4e2d...' : (isEdit ? '\u4fdd\u5b58\u4fee\u6539' : '\u521b\u5efa\u5b9e\u9a8c')}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CourseTabIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="4" width="17" height="16" rx="2.5" />
      <path d="M8 9h8M8 13h8M8 17h5" />
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

export default TeacherDashboard;





