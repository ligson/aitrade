<template>
  <div class="login-page">
    <a-card title="aitrade 登录" class="login-card">
      <a-form layout="vertical" @finish="handleLogin">
        <a-form-item label="用户名" name="username">
          <a-input v-model:value="form.username" placeholder="请输入用户名" />
        </a-form-item>
        <a-form-item label="密码" name="password">
          <a-input-password v-model:value="form.password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item label="图形验证码" name="captchaCode">
          <a-space direction="vertical" style="width: 100%">
            <a-input v-model:value="form.captchaCode" placeholder="请输入验证码" />
            <div class="captcha-row">
              <div class="captcha-image" v-html="captchaSvg"></div>
              <a-button @click="loadCaptcha">刷新验证码</a-button>
            </div>
          </a-space>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="submitting">登录</a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchCaptcha } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const submitting = ref(false)
const captchaSvg = ref('')
const captchaKey = ref('')

const form = reactive({
  username: 'admin',
  password: 'admin123456',
  captchaCode: '',
})

async function loadCaptcha() {
  const data = await fetchCaptcha()
  captchaKey.value = data.captchaKey
  captchaSvg.value = data.captchaSvg
  form.captchaCode = ''
}

async function handleLogin() {
  submitting.value = true
  try {
    await auth.login({
      username: form.username,
      password: form.password,
      captchaKey: captchaKey.value,
      captchaCode: form.captchaCode,
    })
    router.push('/trade-logs')
  } finally {
    submitting.value = false
    await loadCaptcha()
  }
}

onMounted(loadCaptcha)
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
}

.login-card {
  width: 420px;
}

.captcha-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.captcha-image {
  flex: 1;
  min-height: 40px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
</style>
