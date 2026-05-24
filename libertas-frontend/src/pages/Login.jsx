import { useState } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { Box, TextField, Button, Typography, Alert, CircularProgress } from '@mui/material';
import { login } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { loginUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const justRegistered = location.state?.registered;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await login(username, password);
      loginUser(res.data.access_token, res.data.user);
      navigate(res.data.user.is_admin === 1 ? '/admin' : '/chat');
    } catch (err) {
      setError(err.response?.data?.detail || '帳號或密碼錯誤');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%)',
    }}>
      <Box sx={{
        width: 400,
        bgcolor: 'white',
        borderRadius: 4,
        p: 5,
        boxShadow: '0 24px 64px rgba(0,0,0,0.3)',
      }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h4" fontWeight={700} color="#1a237e" gutterBottom>
            利伯他茲
          </Typography>
          <Typography variant="body2" color="text.secondary">
            社工支持助理系統
          </Typography>
        </Box>

        {justRegistered && (
          <Alert severity="success" sx={{ mb: 2 }}>
            註冊成功！請用剛才設定的帳號密碼登入。
          </Alert>
        )}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth label="帳號" value={username}
            onChange={(e) => setUsername(e.target.value)}
            sx={{ mb: 2 }} required
          />
          <TextField
            fullWidth label="密碼" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 3 }} required
          />
          <Button
            fullWidth type="submit" variant="contained" size="large"
            disabled={loading}
            sx={{
              py: 1.5, borderRadius: 2,
              background: 'linear-gradient(135deg, #1a237e, #1565c0)',
              fontSize: '1rem', fontWeight: 600, mb: 2,
            }}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : '登入'}
          </Button>

          <Typography variant="body2" textAlign="center" color="text.secondary">
            還沒有帳號？{' '}
            <Link to="/register" style={{ color: '#1a237e', fontWeight: 600 }}>
              立即註冊
            </Link>
          </Typography>
        </form>
      </Box>
    </Box>
  );
}
