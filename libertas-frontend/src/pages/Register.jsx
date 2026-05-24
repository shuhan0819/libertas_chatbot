import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Box, TextField, Button, Typography,
  Alert, CircularProgress
} from '@mui/material';
import MarkEmailReadIcon from '@mui/icons-material/MarkEmailRead';
import axios from 'axios';

const API_BASE = '/api';

export default function Register() {
  const [form, setForm] = useState({
    display_name: '', email: '', username: '', password: '', confirm_password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm_password) { setError('兩次密碼輸入不一致'); return; }
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/auth/register`, {
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        email: form.email,
      });
      setRegistered(true);
    } catch (err) {
      setError(err.response?.data?.detail || '註冊失敗，請稍後再試');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%)',
    }}>
      <Box sx={{ width: 420, bgcolor: 'white', borderRadius: 4, p: 5, boxShadow: '0 24px 64px rgba(0,0,0,0.3)' }}>

        {registered ? (
          // ── 註冊成功：顯示驗證信提示 ──
          <Box sx={{ textAlign: 'center' }}>
            <MarkEmailReadIcon sx={{ fontSize: 64, color: '#1a237e', mb: 2 }} />
            <Typography variant="h5" fontWeight={700} color="#1a237e" gutterBottom>
              請驗證你的信箱
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 1 }}>
              驗證信已寄至
            </Typography>
            <Typography fontWeight={600} sx={{ mb: 3 }}>
              {form.email}
            </Typography>
            <Alert severity="info" sx={{ mb: 3, textAlign: 'left' }}>
              請到你的 Gmail 收信，點擊「驗證我的信箱」按鈕後，再回來登入。
            </Alert>
            <Button
              fullWidth variant="contained"
              onClick={() => navigate('/login')}
              sx={{
                py: 1.5, borderRadius: 2,
                background: 'linear-gradient(135deg, #1a237e, #1565c0)',
                fontSize: '1rem', fontWeight: 600,
              }}
            >
              前往登入
            </Button>
          </Box>
        ) : (
          // ── 註冊表單 ──
          <>
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Typography variant="h4" fontWeight={700} color="#1a237e" gutterBottom>
                利伯他茲
              </Typography>
              <Typography variant="body2" color="text.secondary">建立你的帳號</Typography>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <form onSubmit={handleSubmit}>
              <TextField fullWidth label="暱稱" name="display_name" value={form.display_name}
                onChange={handleChange} sx={{ mb: 2 }} required placeholder="你希望被稱呼的名字" />
              <TextField fullWidth label="Gmail" name="email" type="email" value={form.email}
                onChange={handleChange} sx={{ mb: 2 }} required placeholder="yourname@gmail.com" />
              <TextField fullWidth label="帳號" name="username" value={form.username}
                onChange={handleChange} sx={{ mb: 2 }} required placeholder="至少 3 個字元" />
              <TextField fullWidth label="密碼" name="password" type="password" value={form.password}
                onChange={handleChange} sx={{ mb: 2 }} required placeholder="至少 6 個字元" />
              <TextField fullWidth label="確認密碼" name="confirm_password" type="password"
                value={form.confirm_password} onChange={handleChange} sx={{ mb: 3 }} required />
              <Button fullWidth type="submit" variant="contained" size="large" disabled={loading}
                sx={{
                  py: 1.5, borderRadius: 2,
                  background: 'linear-gradient(135deg, #1a237e, #1565c0)',
                  fontSize: '1rem', fontWeight: 600, mb: 2,
                }}>
                {loading ? <CircularProgress size={24} color="inherit" /> : '註冊'}
              </Button>
              <Typography variant="body2" textAlign="center" color="text.secondary">
                已有帳號？{' '}
                <Link to="/login" style={{ color: '#1a237e', fontWeight: 600 }}>登入</Link>
              </Typography>
            </form>
          </>
        )}
      </Box>
    </Box>
  );
}
