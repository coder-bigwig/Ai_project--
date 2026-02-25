import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import CourseWorkspacePanel from '../components/CourseWorkspacePanel';
import CourseEditorModal from '../components/CourseEditorModal';
import ExperimentEditorModal from '../components/ExperimentEditorModal';
import TeacherProfilePanel from '../components/TeacherProfilePanel';
import TeacherAIModule from '../components/TeacherAIModule';
import { persistJupyterTokenFromUrl } from '../../../shared/jupyter/jupyterAuth';
import '../styles/TeacherDashboard.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const JUPYTERHUB_URL = process.env.REACT_APP_JUPYTERHUB_URL || '';
const DEFAULT_JUPYTERHUB_URL = `${window.location.origin}/jupyter/hub/home`;
const DEFAULT_JUPYTERHUB_HEALTH_URL = `${window.location.origin}/jupyter/hub/health`;
const LEGACY_JUPYTERHUB_URL = `${window.location.protocol}//${window.location.hostname}:8003/jupyter/hub/home`;
const TABS = [
  { key: 'courses', label: '\u8bfe\u7a0b\u5e93', tip: '\u8bfe\u7a0b\u4e0e\u5b9e\u9a8c\u7ba1\u7406', Icon: CourseTabIcon },
  { key: 'profile', label: '\u4e2a\u4eba\u4e2d\u5fc3', tip: '\u8d26\u53f7\u4e0e\u5b89\u5168\u8bbe\u7f6e', Icon: ProfileTabIcon },
  { key: 'ai', label: 'AI\u529f\u80fd', tip: '\u6a21\u578b\u4e0e\u5bc6\u94a5\u914d\u7f6e', Icon: AITabIcon },
];

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
  const { courseId: routeCourseId = '' } = useParams();
  const normalizedRouteCourseId = String(routeCourseId || '').trim();
  const isCourseDetailRoute = Boolean(normalizedRouteCourseId);
  const tabs = TABS;
  const [activeTab, setActiveTab] = useState('courses');
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

  useEffect(() => {
    if (isCourseDetailRoute && activeTab !== 'courses') {
      setActiveTab('courses');
    }
  }, [activeTab, isCourseDetailRoute]);

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

  const openCourseDetail = useCallback((course) => {
    const courseId = encodeURIComponent(String(course?.id || '').trim());
    if (!courseId) return;
    navigate(`/teacher/course/${courseId}`);
  }, [navigate]);

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
            <span className="teacher-lab-user-role">{'\u89d2\u8272\uff1a\u6559\u5e08\u7ba1\u7406\u5458'}</span>
          </div>
          <button type="button" className="teacher-lab-jhub" onClick={openJupyterHub}>{'\u8fdb\u5165 JupyterHub'}</button>
          <button type="button" className="teacher-lab-logout" onClick={logout}>{'\u9000\u51fa'}</button>
        </div>
      </header>

      <div className={`teacher-lab-layout ${isCourseDetailRoute ? 'course-detail-route' : ''}`}>
        {isCourseDetailRoute ? null : (
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
        )}

        <section className={`teacher-lab-content ${isCourseDetailRoute ? 'course-detail-content' : ''}`}>
          {!isCourseDetailRoute && activeTab !== 'courses' ? <div className="teacher-lab-breadcrumb">{'\u6559\u5e08\u7aef'} / <strong>{currentTab.label}</strong></div> : null}

          {activeTab === 'courses' || isCourseDetailRoute ? (
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
              routeCourseId={normalizedRouteCourseId}
              forceDetail={isCourseDetailRoute}
              onOpenCourse={openCourseDetail}
              onExitDetail={isCourseDetailRoute ? () => navigate('/teacher') : undefined}
            />
          ) : null}

          {!isCourseDetailRoute && activeTab === 'profile' ? (
            <div className="teacher-lab-section">
              <TeacherProfilePanel username={username} userRole={userRole} />
            </div>
          ) : null}

          {!isCourseDetailRoute && activeTab === 'ai' ? (
            <div className="teacher-lab-section">
              <TeacherAIModule username={username} />
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

export default TeacherDashboard;
