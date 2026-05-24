import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, TextField, IconButton, List, ListItem,
  ListItemButton, ListItemText, Divider, CircularProgress,
  Chip, Tooltip, Button, Dialog, DialogTitle, DialogContent,
  DialogActions, Alert
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import MicIcon from '@mui/icons-material/Mic';
import StopIcon from '@mui/icons-material/Stop';
import AddIcon from '@mui/icons-material/Add';
import LogoutIcon from '@mui/icons-material/Logout';
import LockResetIcon from '@mui/icons-material/LockReset';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import PhoneIcon from '@mui/icons-material/Phone';
import CloseIcon from '@mui/icons-material/Close';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import DeleteIcon from '@mui/icons-material/Delete';

import {
  getSessions, createSession, getMessages,
  sendMessage, sendVoice, getTTS, getInstitution,
  deleteSession, changePassword,
} from '../api/client';

const API_BASE = 'http://localhost:8000/api';

export default function Chat() {
  const { user, logoutUser } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [showEmergency, setShowEmergency] = useState(false);
  const [dangerMessageCount, setDangerMessageCount] = useState(0);
  const [institution, setInstitution] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // 標題編輯
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');

  const [pwDialog, setPwDialog] = useState(false);
  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');

  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const bottomRef = useRef(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadSessions(); loadInstitution(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const loadInstitution = async () => {
    try {
      const res = await getInstitution();
      setInstitution(res.data);
    } catch (e) { console.error(e); }
  };

  const loadSessions = async () => {
    const res = await getSessions();
    setSessions(res.data);
    if (res.data.length > 0) selectSession(res.data[0]);
  };

  const selectSession = async (session) => {
    setCurrentSession(session);
    setShowEmergency(false);
    setDangerMessageCount(0);
    setEditingTitle(false);
    const res = await getMessages(session.id);
    setMessages(res.data);
  };

  const newSession = async () => {
    const res = await createSession();
    setSessions(prev => [res.data, ...prev]);
    selectSession(res.data);
  };

  const handleDeleteSession = async (e, sessionId) => {
      e.stopPropagation(); // 防止觸發 selectSession
      if (!window.confirm('確定要刪除這個對話嗎？')) return;
      try {
          await deleteSession(sessionId);
          setSessions(prev => prev.filter(s => s.id !== sessionId));
          if (currentSession?.id === sessionId) {
              setCurrentSession(null);
              setMessages([]);
          }
      } catch (err) {
          console.error(err);
      }
  };

  // 儲存標題
  const saveTitle = async () => {
    if (!titleInput.trim() || !currentSession) return;
    try {
      const token = localStorage.getItem('token');
      await axios.patch(
        `${API_BASE}/chat/sessions/${currentSession.id}/title`,
        { title: titleInput.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const updated = { ...currentSession, title: titleInput.trim() };
      setCurrentSession(updated);
      setSessions(prev => prev.map(s => s.id === updated.id ? updated : s));
    } catch (e) { console.error(e); }
    setEditingTitle(false);
  };

  const handleSend = async () => {
    if (!input.trim() || !currentSession || loading) return;
    const text = input.trim();
    setInput('');
    setLoading(true);
    try {
      const res = await sendMessage(currentSession.id, text);
      setMessages(prev => [...prev, res.data.user_message, res.data.assistant_message]);
      if (res.data.is_danger) {
        setShowEmergency(true);
        setDangerMessageCount(0);
      } else {
        setDangerMessageCount(prev => {
          const next = prev + 1;
          if (next >= 3) setShowEmergency(false);
          return next;
        });
      }
    } catch (err) {
      if (err.response?.status === 503) {
        setMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant',
          content: '⚙️ 系統正在更新知識庫，請稍候幾分鐘後再試。',
          created_at: new Date().toISOString(),
        }]);
      }
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    mediaRef.current = mr;
    chunksRef.current = [];
    mr.ondataavailable = (e) => chunksRef.current.push(e.data);
    mr.onstop = async () => {
      const mimeType = MediaRecorder.isTypeSupported('audio/ogg') ? 'audio/ogg' : 'audio/webm';
      const blob = new Blob(chunksRef.current, { type: mimeType });
      stream.getTracks().forEach(t => t.stop());
      setLoading(true);
      try {
        const res = await sendVoice(currentSession.id, blob);
        setMessages(prev => [...prev, res.data.user_message, res.data.assistant_message]);
        if (res.data.is_danger) {
          setShowEmergency(true);
          setDangerMessageCount(0);
        } else {
          setDangerMessageCount(prev => {
            const next = prev + 1;
            if (next >= 3) setShowEmergency(false);
            return next;
          });
        }
      } catch (err) {
        if (err.response?.status === 503) {
          setMessages(prev => [...prev, {
            id: Date.now(), role: 'assistant',
            content: '⚙️ 系統正在更新知識庫，請稍候幾分鐘後再試。',
            created_at: new Date().toISOString(),
          }]);
        }
      } finally {
        setLoading(false);
      }
    };
    mr.start();
    setRecording(true);
  };

  const stopRecording = () => { mediaRef.current?.stop(); setRecording(false); };

  const handleChangePassword = async () => {
    setPwError('');
    setPwSuccess('');
    if (!oldPw || !newPw) { setPwError('請填寫所有欄位'); return; }
    if (newPw.length < 6) { setPwError('新密碼至少需要 6 個字元'); return; }
    try {
      await changePassword(oldPw, newPw);
      setPwSuccess('密碼已成功修改');
      setOldPw(''); setNewPw('');
      setTimeout(() => { setPwDialog(false); setPwSuccess(''); }, 1500);
    } catch (err) {
      setPwError(err.response?.data?.detail || '修改失敗，請確認舊密碼是否正確');
    }
  };

  const playTTS = async (text) => {
    const res = await getTTS(text);
    new Audio(URL.createObjectURL(res.data)).play();
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#f0f4ff' }}>

      {/* ── 側邊欄收起按鈕（浮動） ── */}
      <IconButton
        onClick={() => setSidebarOpen(!sidebarOpen)}
        sx={{
          position: 'fixed', left: sidebarOpen ? 268 : 8, top: '50%',
          transform: 'translateY(-50%)', zIndex: 100,
          bgcolor: '#1a237e', color: 'white', width: 24, height: 48,
          borderRadius: '0 8px 8px 0',
          '&:hover': { bgcolor: '#283593' },
          transition: 'left 0.3s',
        }}
      >
        {sidebarOpen ? <ChevronLeftIcon /> : <ChevronRightIcon />}
      </IconButton>

      {/* ── 側邊欄 ── */}
      <Box sx={{
        width: sidebarOpen ? 280 : 0,
        bgcolor: '#1a237e', color: 'white',
        display: 'flex', flexDirection: 'column', flexShrink: 0,
        overflow: 'hidden',
        transition: 'width 0.3s',
      }}>
        <Box sx={{ p: 3, borderBottom: '1px solid rgba(255,255,255,0.1)', minWidth: 280 }}>
          <Typography sx={{ fontSize: '1.3rem', fontWeight: 700 }}>利伯他茲助理</Typography>
          <Typography sx={{ fontSize: '1rem', opacity: 0.7, mt: 0.5 }}>{user?.display_name}</Typography>
        </Box>

        <Button
          startIcon={<AddIcon sx={{ fontSize: '1.4rem' }} />}
          onClick={newSession}
          sx={{
            m: 2, py: 1.5, color: 'white', fontSize: '1.05rem', fontWeight: 600,
            border: '1px solid rgba(255,255,255,0.4)', borderRadius: 2, minWidth: 240,
          }}
        >
          新對話
        </Button>

        <List sx={{ flex: 1, overflow: 'auto', py: 0 }}>
          {sessions.map(s => (
            <ListItem key={s.id} disablePadding
              secondaryAction={
                <IconButton
                  size="small"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  sx={{ color: 'rgba(255,255,255,0.4)', '&:hover': { color: '#ff5252' }, mr: 1 }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              }
            >
              <ListItemButton
                selected={currentSession?.id === s.id}
                onClick={() => selectSession(s)}
                sx={{
                  '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.18)' },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                  borderRadius: 1, mx: 1, my: 0.3, py: 1.2,
                }}
              >
                <ListItemText
                  primary={s.title}
                  primaryTypographyProps={{ color: 'white', fontSize: '0.95rem', noWrap: true }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        {/* 機構資訊 */}
        {institution && (institution.address || institution.open_hours || institution.phone) && (
          <>
            <Divider sx={{ borderColor: 'rgba(255,255,255,0.15)' }} />
            <Box sx={{ p: 2, minWidth: 280 }}>
              <Typography sx={{ fontSize: '0.95rem', opacity: 0.6, mb: 1.5, fontWeight: 600, letterSpacing: '0.05em' }}>
                機構資訊
              </Typography>
              {institution.address && (
                <Box sx={{ display: 'flex', gap: 1, mb: 1.2, opacity: 0.85 }}>
                  <LocationOnIcon sx={{ fontSize: '1.2rem', mt: 0.2, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.95rem', lineHeight: 1.5 }}>{institution.address}</Typography>
                </Box>
              )}
              {institution.open_hours && (
                <Box sx={{ display: 'flex', gap: 1, mb: 1.2, opacity: 0.85 }}>
                  <AccessTimeIcon sx={{ fontSize: '1.2rem', mt: 0.2, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.95rem' }}>{institution.open_hours}</Typography>
                </Box>
              )}
              {institution.phone && (
                <Box sx={{ display: 'flex', gap: 1, opacity: 0.85 }}>
                  <PhoneIcon sx={{ fontSize: '1.2rem', mt: 0.2, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.95rem' }}>{institution.phone}</Typography>
                </Box>
              )}
            </Box>
          </>
        )}

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />
        <ListItemButton
          onClick={() => { setPwDialog(true); setPwError(''); setPwSuccess(''); setOldPw(''); setNewPw(''); }}
          sx={{ color: 'rgba(255,255,255,0.7)', py: 1.5, minWidth: 280 }}
        >
          <LockResetIcon sx={{ mr: 1.5, fontSize: '1.3rem' }} />
          <Typography sx={{ fontSize: '1rem' }}>修改密碼</Typography>
        </ListItemButton>
        <ListItemButton
          onClick={() => { logoutUser(); navigate('/login'); }}
          sx={{ color: 'rgba(255,255,255,0.7)', py: 2, minWidth: 280 }}
        >
          <LogoutIcon sx={{ mr: 1.5, fontSize: '1.3rem' }} />
          <Typography sx={{ fontSize: '1rem' }}>登出</Typography>
        </ListItemButton>
      </Box>

      {/* ── 聊天區域 ── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {currentSession ? (
          <>
            {/* 頂部標題（可編輯） */}
            <Box sx={{
              px: 3, py: 2, bgcolor: 'white',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              display: 'flex', alignItems: 'center', gap: 1,
            }}>
              {editingTitle ? (
                <>
                  <TextField
                    value={titleInput}
                    onChange={e => setTitleInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') setEditingTitle(false); }}
                    size="small" autoFocus
                    sx={{ flex: 1, '& input': { fontSize: '1.2rem', fontWeight: 600 } }}
                  />
                  <IconButton onClick={saveTitle} color="primary" size="small">
                    <CheckIcon />
                  </IconButton>
                </>
              ) : (
                <>
                  <Typography sx={{ fontSize: '1.2rem', fontWeight: 600, flex: 1 }}>
                    {currentSession.title}
                  </Typography>
                  <Tooltip title="修改標題">
                    <IconButton
                      size="small" onClick={() => { setEditingTitle(true); setTitleInput(currentSession.title); }}
                      sx={{ opacity: 0.4, '&:hover': { opacity: 1 } }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </>
              )}
            </Box>

            {/* 緊急聯絡按鈕 */}
            {showEmergency && institution?.phone && (
              <Box sx={{
                mx: 3, mt: 2, p: 2, bgcolor: '#ffebee', borderRadius: 2,
                border: '2px solid #d32f2f', display: 'flex',
                alignItems: 'center', justifyContent: 'space-between',
              }}>
                <Box>
                  <Typography sx={{ color: '#d32f2f', fontWeight: 700, fontSize: '1.1rem' }}>
                    🚨 我們已通知社工人員
                  </Typography>
                  <Typography sx={{ color: '#c62828', fontSize: '1rem', mt: 0.3 }}>
                    如需立即協助，請撥打下方電話
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexShrink: 0 }}>
                  <Button
                    variant="contained"
                    startIcon={<PhoneIcon />}
                    href={`tel:${institution.phone}`}
                    sx={{
                      bgcolor: '#d32f2f', '&:hover': { bgcolor: '#b71c1c' },
                      fontSize: '1.1rem', py: 1.5, px: 3, borderRadius: 2,
                    }}
                  >
                    立即聯繫社工
                  </Button>
                  <Tooltip title="關閉通知">
                    <IconButton
                      onClick={() => { setShowEmergency(false); setDangerMessageCount(0); }}
                      sx={{ color: '#d32f2f', '&:hover': { bgcolor: '#ffcdd2' } }}
                    >
                      <CloseIcon />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            )}

            {/* 訊息列表 */}
            <Box sx={{ flex: 1, overflow: 'auto', p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {messages.map(msg => (
                <Box key={msg.id} sx={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}>
                  <Box sx={{
                    maxWidth: '72%',
                    bgcolor: msg.role === 'user' ? '#1a237e' : 'white',
                    color: msg.role === 'user' ? 'white' : 'text.primary',
                    borderRadius: msg.role === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                    p: '16px 22px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
                    position: 'relative',
                    pb: msg.role === 'assistant' ? '44px' : '16px',
                  }}>
                    {msg.audio_filename && (
                      <Chip label="🎤 語音訊息" size="medium"
                        sx={{ mb: 1, display: 'block', fontSize: '1rem', color: 'white', bgcolor: 'rgba(255,255,255,0.2)', border: 'none' }}
                      />
                    )}
                    <Typography sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, fontSize: '1.2rem' }}>
                      {msg.content}
                    </Typography>
                    {msg.role === 'assistant' && (
                      <Tooltip title="播放語音">
                        <IconButton
                          onClick={() => playTTS(msg.content)}
                          sx={{ position: 'absolute', bottom: 8, right: 10, opacity: 0.4, '&:hover': { opacity: 1 } }}
                        >
                          <VolumeUpIcon sx={{ fontSize: '1.3rem' }} />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              ))}

              {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <Box sx={{
                    bgcolor: 'white', borderRadius: '20px', p: '14px 20px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
                    display: 'flex', gap: '6px', alignItems: 'center'
                  }}>
                    {[0, 1, 2].map(i => (
                      <Box key={i} sx={{
                        width: 8, height: 8, bgcolor: '#90a4ae', borderRadius: '50%',
                        animation: 'bounce 1.2s infinite',
                        animationDelay: `${i * 0.2}s`,
                        '@keyframes bounce': {
                          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: 0.4 },
                          '40%': { transform: 'scale(1)', opacity: 1 },
                        }
                      }} />
                    ))}
                  </Box>
                </Box>
              )}
              <div ref={bottomRef} />
            </Box>

            {/* 輸入區 */}
            <Box sx={{ p: 2.5, bgcolor: 'white', boxShadow: '0 -2px 8px rgba(0,0,0,0.05)' }}>
              <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-end' }}>
                <TextField
                  fullWidth multiline maxRows={4}
                  placeholder="輸入訊息..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  sx={{
                    '& .MuiOutlinedInput-root': { borderRadius: 3, fontSize: '1.2rem' },
                    '& textarea': { fontSize: '1.2rem', lineHeight: 1.7 },
                  }}
                />
                <Tooltip title={recording ? '停止錄音' : '語音輸入'}>
                  <IconButton
                    color={recording ? 'error' : 'default'}
                    onClick={recording ? stopRecording : startRecording}
                    disabled={!currentSession || loading}
                    sx={{ width: 56, height: 56, flexShrink: 0, bgcolor: recording ? '#ffebee' : '#f5f5f5', '&:hover': { bgcolor: recording ? '#ffcdd2' : '#eeeeee' } }}
                  >
                    {recording ? <StopIcon sx={{ fontSize: '1.8rem' }} /> : <MicIcon sx={{ fontSize: '1.8rem' }} />}
                  </IconButton>
                </Tooltip>
                <IconButton
                  onClick={handleSend}
                  disabled={!input.trim() || loading}
                  sx={{ width: 56, height: 56, flexShrink: 0, bgcolor: '#1a237e', color: 'white', '&:hover': { bgcolor: '#283593' }, '&:disabled': { bgcolor: '#e0e0e0' } }}
                >
                  <SendIcon sx={{ fontSize: '1.6rem' }} />
                </IconButton>
              </Box>
              {recording && (
                <Box sx={{ mt: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 12, height: 12, bgcolor: 'error.main', borderRadius: '50%' }} />
                  <Typography sx={{ color: 'error.main', fontSize: '1.1rem' }}>錄音中⋯ 點停止按鈕結束</Typography>
                </Box>
              )}
            </Box>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography sx={{ fontSize: '1.4rem', color: 'text.secondary', mb: 2 }}>歡迎使用利伯他茲助理</Typography>
              <Button variant="contained" startIcon={<AddIcon />} onClick={newSession}
                sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)', borderRadius: 2, fontSize: '1.1rem', py: 1.5, px: 3 }}>
                開始新對話
              </Button>
            </Box>
          </Box>
        )}
      </Box>

      {/* 修改密碼 Dialog */}
      <Dialog open={pwDialog} onClose={() => setPwDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>修改密碼</DialogTitle>
        <DialogContent>
          {pwError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{pwError}</Alert>}
          {pwSuccess && <Alert severity="success" sx={{ mb: 2, mt: 1 }}>{pwSuccess}</Alert>}
          <TextField
            fullWidth label="舊密碼" type="password" value={oldPw}
            onChange={e => setOldPw(e.target.value)}
            sx={{ mt: 1, mb: 2 }} autoFocus
          />
          <TextField
            fullWidth label="新密碼" type="password" value={newPw}
            onChange={e => setNewPw(e.target.value)}
            placeholder="至少 6 個字元"
            onKeyDown={e => { if (e.key === 'Enter') handleChangePassword(); }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setPwDialog(false)}>取消</Button>
          <Button variant="contained" onClick={handleChangePassword}
            sx={{ background: 'linear-gradient(135deg, #1a237e, #1565c0)' }}>
            確認修改
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
