import React, { useState } from 'react';

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 413) return '\u9644\u4ef6\u8fc7\u5927\uff0c\u8bf7\u538b\u7f29\u540e\u91cd\u8bd5\uff08\u5f53\u524d\u9650\u5236 200MB\uff09';
  return error?.response?.data?.detail || fallback;
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

export default CourseEditorModal;
