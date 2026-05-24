import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Tabs, Tab, Table, TableHead, TableBody,
  TableRow, TableCell, TableContainer, Paper, Button,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Chip, IconButton, Select, MenuItem,
  FormControl, Alert, Tooltip, LinearProgress
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ChatIcon from '@mui/icons-material/Chat';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import WarningIcon from '@mui/icons-material/Warning';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import SaveIcon from '@mui/icons-material/Save';
import BlockIcon from '@mui/icons-material/Block';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import LockResetIcon from '@mui/icons-material/LockReset';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import {
  getUsers, createUser,
  getUserSessions, getSessionMessages,
  getDangerEvents, updateDangerStatus,
  getInstitution, updateInstitution,
  rebuildKB, getKBStatus,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = '/api';
const authHeader = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

// 危險等級設定
const LEVEL_CONFIG = {
  crisis:  { label: '立即處理', emoji: '🚨', color: 'error',   bg: '#ffebee', border: '#b71c1c' },
  concern: { label: '需要關注', emoji: '⚠️', color: 'warning', bg: '#fff3e0', border: '#e65100' },
  notice:  { label: '留意',     emoji: '📋', color: 'info',    bg: '#e3f2fd', border: '#1565c0' },
};

export default function AdminDashboard() {
  const { user, logoutUser } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [users, setUsers] = useState([]);
  const [dangerEvents, setDangerEvents] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [createDialog, setCreateDialog] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', password: '', display_name: '', email: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deleteDialog, setDeleteDialog] = useState({ open: false, user: null, type: null });
  const [resetDialog, setResetDialog] = useState({ open: false, user: null });
  const [newPassword, setNewPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const [institution, setInstitution] = useState({
    name: '', address: '', phone: '', open_hours: '', alert_emails: '',
    gmail_user: '', gmail_app_password: ''
  });
  const [instSaving, setInstSaving] = useState(false);
  const [kbStatus, setKbStatus] = useState({ is_rebuilding: false, progress: 0, stage: '', last_rebuilt: null, error: null });
  const [levelFilter, setLevelFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [convDialog, setConvDialog] = useState({ open: false, event: null });
  const kbPollRef = useRef(null);
  const dangerPollRef = useRef(null);

  // 解析 full_conversation（支援 JSON 與舊版 Python repr 格式）
  const parseConversation = (raw) => {
    if (!raw) return [];
    try { return JSON.parse(raw); } catch {}
    try {
      return JSON.parse(
        raw.replace(/'/g, '"').replace(/\bTrue\b/g, 'true')
          .replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null')
      );
    } catch { return []; }
  };

  // 根據 user_id 查找顯示名稱
  const getUserName = (userId) => {
    const u = users.find(u => u.id === userId);
    return u ? u.display_name : `用戶 ${userId}`;
  };

  // 根據觸發關鍵字判斷等級（若後端有回傳 level 欄位則優先使用）
  const getDangerLevel = (event) => {
    if (event.level) return event.level;
    // 向下相容：根據 status 推測
    return 'notice';
  };

  // 篩選後的危險事件
  const filteredEvents = dangerEvents.filter(e => {
    if (levelFilter && getDangerLevel(e) !== levelFilter) return false;
    if (statusFilter && e.status !== statusFilter) return false;
    if (dateFrom && new Date(e.notified_at + 'Z') < new Date(dateFrom)) return false;
    if (dateTo && new Date(e.notified_at + 'Z') > new Date(dateTo + 'T23:59:59Z')) return false;
    return true;
  });



  // 危險訊號自動刷新（每30秒）
  useEffect(() => {
    if (tab === 2) {
      dangerPollRef.current = setInterval(() => {
        loadDangerEvents();
      }, 30000);
    }
    return () => {
      if (dangerPollRef.current) {
        clearInterval(dangerPollRef.current);
        dangerPollRef.current = null;
      }
    };
  }, [tab]);

  const startKBPoll = () => {
    if (kbPollRef.current) return;
    kbPollRef.current = setInterval(async () => {
      try {
        const res = await getKBStatus();
        setKbStatus(res.data);
        if (!res.data.is_rebuilding) {
          clearInterval(kbPollRef.current);
          kbPollRef.current = null;
          if (res.data.stage === '重建完成') setSuccess('✅ 知識庫重建完成！');
          if (res.data.error) setError(`知識庫重建失敗：${res.data.error}`);
        }
      } catch (e) { console.error(e); }
    }, 3000);
  };

  const handleRebuildKB = async () => {
    setError('');
    try {
      await rebuildKB();
      setKbStatus({ is_rebuilding: true, progress: 5, stage: '準備中...', last_rebuilt: null, error: null });
      startKBPoll();
    } catch (e) {
      setError(e.response?.data?.detail || '重建失敗');
    }
  };

  useEffect(() => {
    loadUsers();
    loadDangerEvents();
    loadInstitution();
    getKBStatus().then(res => setKbStatus(res.data)).catch(console.error);
  }, []);

  const loadUsers = async () => { const res = await getUsers(); setUsers(res.data); };
  const loadDangerEvents = async () => { const res = await getDangerEvents(); setDangerEvents(res.data); };
  const loadInstitution = async () => {
    try {
      const res = await getInstitution();
      setInstitution({
        name: res.data.name || '', address: res.data.address || '',
        phone: res.data.phone || '', open_hours: res.data.open_hours || '',
        alert_emails: res.data.alert_emails || '',
        gmail_user: res.data.gmail_user || '', gmail_app_password: res.data.gmail_app_password || ''
      });
    } catch (e) { console.error(e); }
  };

  const handleSaveInstitution = async () => {
    setInstSaving(true);
    try { await updateInstitution(institution); setSuccess('機構設定已儲存'); setTimeout(() => setSuccess(''), 3000); }
    catch (e) { setError('儲存失敗'); }
    finally { setInstSaving(false); }
  };

  const handleSelectUser = async (u) => {
    setSelectedUser(u); setSelectedSession(null); setMessages([]);
    const res = await getUserSessions(u.id); setSessions(res.data);
  };

  const handleSelectSession = async (s) => {
    setSelectedSession(s); const res = await getSessionMessages(s.id); setMessages(res.data);
  };

  const handleCreateUser = async () => {
    setError('');
    try {
      await createUser({ ...newUser, is_admin: 0 });
      setSuccess(`帳號 ${newUser.username} 建立成功`);
      setCreateDialog(false);
      setNewUser({ username: '', password: '', display_name: '', email: '' });
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) { setError(e.response?.data?.detail || '建立失敗'); }
  };

  const handleDeactivate = async (userId) => {
    try {
      await axios.patch(`${API_BASE}/admin/users/${userId}/deactivate`, {}, authHeader());
      setSuccess('帳號已停用，記錄完整保留');
      setDeleteDialog({ open: false, user: null, type: null });
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) { setError(e.response?.data?.detail || '操作失敗'); }
  };

  const handleActivate = async (userId) => {
    try {
      await axios.patch(`${API_BASE}/admin/users/${userId}/activate`, {}, authHeader());
      setSuccess('帳號已重新啟用');
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) { setError(e.response?.data?.detail || '操作失敗'); }
  };

  const handleHardDelete = async (userId) => {
    try {
      await axios.delete(`${API_BASE}/admin/users/${userId}`, authHeader());
      setSuccess('帳號及所有記錄已永久刪除');
      setDeleteDialog({ open: false, user: null, type: null });
      if (selectedUser?.id === userId) { setSelectedUser(null); setSessions([]); setMessages([]); }
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) { setError(e.response?.data?.detail || '刪除失敗'); }
  };

  const handleResetPassword = async () => {
    setResetError('');
    if (newPassword.length < 6) { setResetError('密碼至少需要 6 個字元'); return; }
    try {
      await axios.patch(`${API_BASE}/admin/users/${resetDialog.user?.id}/reset-password`,
        { new_password: newPassword }, authHeader());
      setSuccess(`${resetDialog.user?.display_name} 的密碼已重設`);
      setResetDialog({ open: false, user: null });
      setNewPassword('');
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) { setResetError(e.response?.data?.detail || '重設失敗'); }
  };

  const handleUpdateDanger = async (eventId, status) => {
    await updateDangerStatus(eventId, status); loadDangerEvents();
  };

  const pendingCount = dangerEvents.filter(e => e.status === '未處理').length;

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#f5f7ff' }}>
      {/* 側邊欄 */}
      <Box sx={{ width: 220, bgcolor: '#1a237e', color: 'white', display: 'flex', flexDirection: 'column', p: 2 }}>
        <Typography variant="h6" fontWeight={700} sx={{ mb: 0.5 }}>利伯他茲</Typography>
        <Typography variant="caption" sx={{ opacity: 0.7, mb: 3 }}>社工管理後台</Typography>
        <Typography variant="caption" sx={{ opacity: 0.5, mb: 1 }}>已登入：{user?.display_name}</Typography>
        <Box sx={{ flex: 1 }} />
        <Button startIcon={<LogoutIcon />} onClick={() => { logoutUser(); navigate('/login'); }}
          sx={{ color: 'rgba(255,255,255,0.7)', justifyContent: 'flex-start' }}>登出</Button>
      </Box>

      {/* 主內容 */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ bgcolor: 'white', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', px: 3 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label="使用者管理" />
            <Tab label="對話記錄" />
            <Tab label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                危險訊號
                {pendingCount > 0 && <Chip label={pendingCount} size="small" color="error" sx={{ height: 18, fontSize: 10 }} />}
              </Box>
            } />
            <Tab label="機構設定" icon={<SettingsIcon fontSize="small" />} iconPosition="start" />
            <Tab label="知識庫" icon={<AutorenewIcon fontSize="small" />} iconPosition="start" />
          </Tabs>
        </Box>

        {success && <Alert severity="success" sx={{ mx: 3, mt: 2 }}>{success}</Alert>}
        {error && <Alert severity="error" sx={{ mx: 3, mt: 2 }} onClose={() => setError('')}>{error}</Alert>}

        {/* ── Tab 0：使用者管理 ── */}
        {tab === 0 && (
          <Box sx={{ p: 3, overflow: 'auto' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6" fontWeight={600}>服務對象帳號</Typography>
              <Button variant="contained" startIcon={<PersonAddIcon />} onClick={() => setCreateDialog(true)}
                sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)', borderRadius: 2 }}>新增帳號</Button>
            </Box>
            <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
              <Table>
                <TableHead sx={{ bgcolor: '#f0f4ff' }}>
                  <TableRow>
                    <TableCell>顯示名稱</TableCell><TableCell>帳號</TableCell><TableCell>Gmail</TableCell>
                    <TableCell>狀態</TableCell><TableCell>建立時間</TableCell><TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {users.map(u => (
                    <TableRow key={u.id} hover sx={{ opacity: !u.is_active && u.is_active !== null ? 0.5 : 1 }}>
                      <TableCell>{u.display_name}</TableCell>
                      <TableCell>{u.username}</TableCell>
                      <TableCell>{u.email || '-'}</TableCell>
                      <TableCell>
                        <Chip label={!u.is_active && u.is_active !== null ? '已停用' : '使用中'}
                          color={!u.is_active && u.is_active !== null ? 'default' : 'success'} size="small" />
                      </TableCell>
                      <TableCell>{new Date(u.created_at).toLocaleDateString('zh-TW')}</TableCell>
                      <TableCell align="right">
                        <Tooltip title="查看對話">
                          <IconButton size="small" onClick={() => { setTab(1); handleSelectUser(u); }}>
                            <ChatIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="重設密碼">
                          <IconButton size="small" color="primary"
                            onClick={() => { setResetDialog({ open: true, user: u }); setNewPassword(''); setResetError(''); }}>
                            <LockResetIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {!u.is_active && u.is_active !== null ? (
                          <Tooltip title="重新啟用帳號">
                            <IconButton size="small" color="success" onClick={() => handleActivate(u.id)}>
                              <CheckCircleIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : (
                          <>
                            <Tooltip title="停用帳號（保留記錄）">
                              <IconButton size="small" color="warning"
                                onClick={() => setDeleteDialog({ open: true, user: u, type: 'deactivate' })}>
                                <BlockIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="永久刪除（清除所有記錄）">
                              <IconButton size="small" color="error"
                                onClick={() => setDeleteDialog({ open: true, user: u, type: 'delete' })}>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {users.length === 0 && (
                    <TableRow><TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>尚無服務對象帳號</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* ── Tab 1：對話記錄 ── */}
        {tab === 1 && (
          <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden', p: 3, gap: 2 }}>
            <Paper sx={{ width: 200, overflow: 'auto', borderRadius: 2, p: 1 }}>
              <Typography variant="subtitle2" sx={{ px: 1, py: 0.5, color: 'text.secondary' }}>使用者</Typography>
              {users.map(u => (
                <Box key={u.id} onClick={() => handleSelectUser(u)}
                  sx={{ px: 1.5, py: 1, borderRadius: 1, cursor: 'pointer', bgcolor: selectedUser?.id === u.id ? '#e8eaf6' : 'transparent', '&:hover': { bgcolor: '#f0f4ff' }, opacity: !u.is_active && u.is_active !== null ? 0.6 : 1 }}>
                  <Typography variant="body2" fontWeight={selectedUser?.id === u.id ? 600 : 400}>
                    {u.display_name}
                    {!u.is_active && u.is_active !== null && <span style={{ fontSize: '0.7rem', color: '#999', marginLeft: 4 }}>(停用)</span>}
                  </Typography>
                </Box>
              ))}
            </Paper>
            {selectedUser && (
              <Paper sx={{ width: 200, overflow: 'auto', borderRadius: 2, p: 1 }}>
                <Typography variant="subtitle2" sx={{ px: 1, py: 0.5, color: 'text.secondary' }}>{selectedUser.display_name} 的對話</Typography>
                {sessions.map(s => (
                  <Box key={s.id} onClick={() => handleSelectSession(s)}
                    sx={{ px: 1.5, py: 1, borderRadius: 1, cursor: 'pointer', bgcolor: selectedSession?.id === s.id ? '#e8eaf6' : 'transparent', '&:hover': { bgcolor: '#f0f4ff' } }}>
                    <Typography variant="body2" noWrap fontWeight={selectedSession?.id === s.id ? 600 : 400}>{s.title}</Typography>
                    <Typography variant="caption" color="text.secondary">{new Date(s.started_at).toLocaleDateString('zh-TW')}</Typography>
                  </Box>
                ))}
              </Paper>
            )}
            {selectedSession && (
              <Paper sx={{ flex: 1, overflow: 'auto', borderRadius: 2, p: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 2, color: 'text.secondary' }}>{selectedSession.title}</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {messages.map(msg => (
                    <Box key={msg.id} sx={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                      <Box sx={{ maxWidth: '70%', borderRadius: 2, p: 1.5, bgcolor: msg.role === 'user' ? '#e8eaf6' : '#f5f5f5' }}>
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                          {msg.role === 'user' ? selectedUser?.display_name : '助理'}
                        </Typography>
                        {msg.audio_filename && <Chip icon={<ChatIcon />} label="語音訊息" size="small" sx={{ mb: 0.5 }} />}
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{msg.content}</Typography>
                        {msg.audio_url && (
                          <Button size="small" onClick={async () => {
                            const token = localStorage.getItem('token');
                            const res = await fetch(`${msg.audio_url}`, { headers: { Authorization: `Bearer ${token}` } });
                            const blob = await res.blob();
                            new Audio(URL.createObjectURL(blob)).play();
                          }} sx={{ mt: 0.5, fontSize: 11 }}>▶ 聽語音</Button>
                        )}
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Paper>
            )}
          </Box>
        )}

        {/* ── Tab 2：危險訊號 ── */}
        {tab === 2 && (
          <Box sx={{ p: 3, overflow: 'auto' }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
              <Typography variant="h6" fontWeight={600}>危險訊號事件</Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<AutorenewIcon />}
                onClick={loadDangerEvents}
                sx={{ borderColor: "#e65100", color: "#e65100", "&:hover": { bgcolor: "#fff3e0" } }}
              >
                刷新
              </Button>
            </Box>

            {/* 篩選列 */}
            <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <Select value={levelFilter} onChange={e => setLevelFilter(e.target.value)} displayEmpty>
                  <MenuItem value="">全部等級</MenuItem>
                  <MenuItem value="crisis">🚨 立即處理</MenuItem>
                  <MenuItem value="concern">⚠️ 需要關注</MenuItem>
                  <MenuItem value="notice">📋 留意</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} displayEmpty>
                  <MenuItem value="">全部狀態</MenuItem>
                  <MenuItem value="未處理">未處理</MenuItem>
                  <MenuItem value="已處理">已處理</MenuItem>
                </Select>
              </FormControl>
              <TextField size="small" type="date" label="從" value={dateFrom}
                onChange={e => setDateFrom(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ minWidth: 150 }} />
              <TextField size="small" type="date" label="至" value={dateTo}
                onChange={e => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ minWidth: 150 }} />
              {(levelFilter || statusFilter || dateFrom || dateTo) && (
                <Button size="small" variant="outlined" color="inherit"
                  onClick={() => { setLevelFilter(''); setStatusFilter(''); setDateFrom(''); setDateTo(''); }}>
                  清除篩選
                </Button>
              )}
              <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
                顯示 {filteredEvents.length} / {dangerEvents.length} 筆
              </Typography>
            </Box>

            {/* 等級說明 */}
            <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
              {Object.entries(LEVEL_CONFIG).map(([key, cfg]) => (
                <Box key={key} sx={{ display: 'flex', alignItems: 'center', gap: 0.5,
                  px: 1.5, py: 0.5, borderRadius: 2, bgcolor: cfg.bg,
                  border: `1px solid ${cfg.border}`, fontSize: 13 }}>
                  <span>{cfg.emoji}</span>
                  <span style={{ color: cfg.border, fontWeight: 600 }}>{cfg.label}</span>
                </Box>
              ))}
            </Box>

            <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
              <Table>
                <TableHead sx={{ bgcolor: '#fff3e0' }}>
                  <TableRow>
                    <TableCell>時間</TableCell>
                    <TableCell>使用者</TableCell>
                    <TableCell>等級</TableCell>
                    <TableCell>觸發關鍵字</TableCell>
                    <TableCell>狀態</TableCell>
                    <TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredEvents.map(e => {
                    const lvl = getDangerLevel(e);
                    const cfg = LEVEL_CONFIG[lvl] || LEVEL_CONFIG['notice'];
                    return (
                      <TableRow key={e.id} sx={{ bgcolor: e.status === '未處理' ? '#fff8f0' : 'transparent' }}>
                        <TableCell>{new Date(e.notified_at + 'Z').toLocaleString('zh-TW')}</TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>
                            {getUserName(e.user_id)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5,
                            px: 1, py: 0.3, borderRadius: 1.5,
                            bgcolor: cfg.bg, border: `1px solid ${cfg.border}`,
                            fontSize: 12, fontWeight: 600, color: cfg.border }}>
                            {cfg.emoji} {cfg.label}
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip icon={<WarningIcon />} label={e.triggered_keyword}
                            size="small"
                            sx={{ bgcolor: cfg.bg, color: cfg.border,
                              '& .MuiChip-icon': { color: cfg.border } }} />
                        </TableCell>
                        <TableCell>
                          <Chip label={e.status}
                            color={e.status === '未處理' ? 'warning' : 'success'} size="small" />
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="查看完整對話">
                            <IconButton size="small" onClick={() => setConvDialog({ open: true, event: e })} sx={{ mr: 0.5 }}>
                              <ChatIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <FormControl size="small" sx={{ minWidth: 100 }}>
                            <Select value={e.status} onChange={(ev) => handleUpdateDanger(e.id, ev.target.value)}>
                              <MenuItem value="未處理">未處理</MenuItem>
                              <MenuItem value="已處理">已處理</MenuItem>
                            </Select>
                          </FormControl>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {filteredEvents.length === 0 && (
                    <TableRow><TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                      {dangerEvents.length === 0 ? '目前無危險訊號事件' : '沒有符合篩選條件的事件'}
                    </TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* ── Tab 3：機構設定 ── */}
        {tab === 3 && (
          <Box sx={{ p: 3, overflow: 'auto', maxWidth: 600 }}>
            <Typography variant="h6" fontWeight={600} sx={{ mb: 3 }}>機構設定</Typography>
            <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>基本資訊</Typography>
              <TextField fullWidth label="機構名稱" value={institution.name} onChange={e => setInstitution({ ...institution, name: e.target.value })} sx={{ mb: 2 }} />
              <TextField fullWidth label="機構地址" value={institution.address} onChange={e => setInstitution({ ...institution, address: e.target.value })} sx={{ mb: 2 }} placeholder="例：台北市中正區○○路○號" />
              <TextField fullWidth label="開放時間" value={institution.open_hours} onChange={e => setInstitution({ ...institution, open_hours: e.target.value })} sx={{ mb: 2 }} placeholder="例：週一至週五 09:00-17:00" />
            </Paper>
            <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>緊急聯絡</Typography>
              <TextField fullWidth label="社工緊急聯絡電話" value={institution.phone} onChange={e => setInstitution({ ...institution, phone: e.target.value })} sx={{ mb: 2 }} placeholder="例：02-1234-5678" />
              <TextField fullWidth label="危險訊號通報 Email（多個用逗號分隔）" value={institution.alert_emails} onChange={e => setInstitution({ ...institution, alert_emails: e.target.value })} placeholder="例：social1@gmail.com, social2@gmail.com" multiline rows={2} />
            </Paper>
            <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Gmail 寄件設定</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                設定用來寄送危險訊號通報的 Gmail 帳號，需先在 Google 帳號開啟兩步驟驗證並建立應用程式密碼。
              </Typography>
              <TextField fullWidth label="寄件 Gmail 帳號" value={institution.gmail_user || ''}
                onChange={e => setInstitution({ ...institution, gmail_user: e.target.value })}
                sx={{ mb: 2 }} placeholder="例：libertas.notify@gmail.com" />
              <TextField fullWidth label="Gmail 應用程式密碼" type="password"
                value={institution.gmail_app_password || ''}
                onChange={e => setInstitution({ ...institution, gmail_app_password: e.target.value })}
                placeholder="16 位數應用程式密碼" />
            </Paper>
            <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSaveInstitution} disabled={instSaving}
              sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)', borderRadius: 2, fontSize: '1rem', py: 1.5, px: 4 }}>
              {instSaving ? '儲存中...' : '儲存設定'}
            </Button>
          </Box>
        )}

        {/* ── Tab 4：知識庫重建 ── */}
        {tab === 4 && (
          <Box sx={{ p: 3, overflow: 'auto', maxWidth: 600 }}>
            <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>知識庫管理</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              重建知識庫會重新讀取 Google Drive 的文件並更新向量索引。重建期間使用者無法傳送訊息。
            </Typography>
            {kbStatus.last_rebuilt && !kbStatus.is_rebuilding && (
              <Alert severity="success" sx={{ mb: 3 }}>上次重建時間：{kbStatus.last_rebuilt}</Alert>
            )}
            {kbStatus.error && (
              <Alert severity="error" sx={{ mb: 3 }}>重建失敗：{kbStatus.error}</Alert>
            )}
            {kbStatus.is_rebuilding ? (
              <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
                <Typography fontWeight={600} sx={{ mb: 1 }}>🔄 {kbStatus.stage || '重建中...'}</Typography>
                <LinearProgress variant="determinate" value={kbStatus.progress} sx={{ height: 10, borderRadius: 5, mb: 1 }} />
                <Typography variant="body2" color="text.secondary">{kbStatus.progress}%</Typography>
              </Paper>
            ) : (
              <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
                <Typography fontWeight={600} sx={{ mb: 1 }}>重建狀態</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{kbStatus.stage || '就緒'}</Typography>
                <LinearProgress variant="determinate" value={kbStatus.progress} sx={{ height: 10, borderRadius: 5 }} />
              </Paper>
            )}
            <Button variant="contained" startIcon={<AutorenewIcon />} onClick={handleRebuildKB}
              disabled={kbStatus.is_rebuilding}
              sx={{ background: kbStatus.is_rebuilding ? '#9e9e9e' : 'linear-gradient(135deg, #1a237e, #1565c0)', borderRadius: 2, fontSize: '1rem', py: 1.5, px: 4 }}>
              {kbStatus.is_rebuilding ? '重建中，請稍候...' : '開始重建知識庫'}
            </Button>
          </Box>
        )}
      </Box>

      {/* 新增帳號 Dialog */}
      <Dialog open={createDialog} onClose={() => setCreateDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>新增服務對象帳號</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <TextField fullWidth label="顯示名稱" value={newUser.display_name} onChange={e => setNewUser({ ...newUser, display_name: e.target.value })} sx={{ mt: 1, mb: 2 }} />
          <TextField fullWidth label="Gmail（選填）" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} type="email" placeholder="example@gmail.com" sx={{ mb: 2 }} />
          <TextField fullWidth label="帳號" value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} sx={{ mb: 2 }} />
          <TextField fullWidth label="密碼" type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => { setCreateDialog(false); setError(''); }}>取消</Button>
          <Button variant="contained" onClick={handleCreateUser} sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)' }}>建立帳號</Button>
        </DialogActions>
      </Dialog>

      {/* 重設密碼 Dialog */}
      <Dialog open={resetDialog.open} onClose={() => { setResetDialog({ open: false, user: null }); setNewPassword(''); setResetError(''); }} maxWidth="xs" fullWidth>
        <DialogTitle>重設密碼</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 2 }}>為「<strong>{resetDialog.user?.display_name}</strong>」設定新密碼</Typography>
          {resetError && <Alert severity="error" sx={{ mb: 2 }}>{resetError}</Alert>}
          <TextField fullWidth label="新密碼" type="password" value={newPassword}
            onChange={e => setNewPassword(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleResetPassword(); }}
            placeholder="至少 6 個字元" autoFocus />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => { setResetDialog({ open: false, user: null }); setNewPassword(''); setResetError(''); }}>取消</Button>
          <Button variant="contained" onClick={handleResetPassword} sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)' }}>確認重設</Button>
        </DialogActions>
      </Dialog>

      {/* 完整對話 Dialog */}
      <Dialog open={convDialog.open} onClose={() => setConvDialog({ open: false, event: null })} maxWidth="sm" fullWidth>
        <DialogTitle>
          完整對話記錄
          {convDialog.event && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {getUserName(convDialog.event.user_id)} ·{' '}
              {new Date(convDialog.event.notified_at + 'Z').toLocaleString('zh-TW')}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent dividers sx={{ maxHeight: 480 }}>
          {parseConversation(convDialog.event?.full_conversation).length === 0 ? (
            <Typography color="text.secondary" align="center" sx={{ py: 4 }}>無對話記錄</Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {parseConversation(convDialog.event?.full_conversation).map((msg, i) => (
                <Box key={i} sx={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <Box sx={{
                    maxWidth: '78%', borderRadius: 2, p: 1.5,
                    bgcolor: msg.role === 'user' ? '#e8eaf6' : '#f5f5f5',
                  }}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5, fontWeight: 600 }}>
                      {msg.role === 'user' ? getUserName(convDialog.event?.user_id) : '助理'}
                    </Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                      {msg.content}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConvDialog({ open: false, event: null })}>關閉</Button>
        </DialogActions>
      </Dialog>

      {/* 停用/刪除確認 Dialog */}
      <Dialog open={deleteDialog.open} onClose={() => setDeleteDialog({ open: false, user: null, type: null })} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ color: deleteDialog.type === 'delete' ? '#d32f2f' : '#e65100' }}>
          {deleteDialog.type === 'delete' ? '⚠️ 永久刪除帳號' : '停用帳號'}
        </DialogTitle>
        <DialogContent>
          {deleteDialog.type === 'delete' ? (
            <Box>
              <Typography sx={{ mb: 1 }}>確定要永久刪除「<strong>{deleteDialog.user?.display_name}</strong>」的帳號嗎？</Typography>
              <Alert severity="error">此操作將同時刪除該使用者的所有對話記錄和危險訊號記錄，<strong>無法復原</strong>。</Alert>
            </Box>
          ) : (
            <Box>
              <Typography sx={{ mb: 1 }}>確定要停用「<strong>{deleteDialog.user?.display_name}</strong>」的帳號嗎？</Typography>
              <Alert severity="warning">停用後該使用者將無法登入，但所有對話和危險訊號記錄會完整保留。可以隨時重新啟用。</Alert>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteDialog({ open: false, user: null, type: null })}>取消</Button>
          <Button variant="contained" color={deleteDialog.type === 'delete' ? 'error' : 'warning'}
            onClick={() => deleteDialog.type === 'delete' ? handleHardDelete(deleteDialog.user?.id) : handleDeactivate(deleteDialog.user?.id)}>
            {deleteDialog.type === 'delete' ? '確認永久刪除' : '確認停用'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}