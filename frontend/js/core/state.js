export const AppState = (() => {
  const _state = {
    user: null,
    accessToken: null,
  };

  function getToken() {
    return _state.accessToken || localStorage.getItem('access_token');
  }
  
  function setAuth(user, access) {
    _state.user = user;
    _state.accessToken = access;
    localStorage.setItem('access_token', access);
    localStorage.setItem('user', JSON.stringify(user));
  }
  
  function clearAuth() {
    _state.user = null;
    _state.accessToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  }
  
  function getUser() {
    return _state.user || JSON.parse(localStorage.getItem('user') || 'null');
  }

  return { getToken, setAuth, clearAuth, getUser, state: _state };
})();
