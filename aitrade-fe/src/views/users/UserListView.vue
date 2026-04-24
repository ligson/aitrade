<template>
  <a-card>
    <a-space direction="vertical" style="width: 100%">
      <a-space wrap>
        <a-input v-model:value="keyword" placeholder="搜索用户名/邮箱/昵称" style="width: 260px" />
        <a-button type="primary" @click="loadUsers">查询</a-button>
        <a-button @click="openCreate">新增用户</a-button>
      </a-space>
      <a-table :data-source="rows" :columns="columns" :pagination="pagination" row-key="id" :loading="loading" :scroll="{ x: 'max-content' }" @change="handleTableChange">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'red'">{{ record.status }}</a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button type="link" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" @click="openResetPassword(record)">重置密码</a-button>
              <a-button type="link" @click="toggleStatus(record)">{{ record.status === 'active' ? '锁定' : '启用' }}</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-space>

    <a-modal v-model:open="editOpen" :title="editingId ? '编辑用户' : '新增用户'" @ok="submitUser" :confirm-loading="submitting">
      <a-form layout="vertical">
        <a-form-item v-if="!editingId" label="用户名"><a-input v-model:value="editForm.username" /></a-form-item>
        <a-form-item label="邮箱"><a-input v-model:value="editForm.email" /></a-form-item>
        <a-form-item label="昵称"><a-input v-model:value="editForm.nickname" /></a-form-item>
        <a-form-item label="备注"><a-input v-model:value="editForm.remark" /></a-form-item>
        <a-form-item v-if="!editingId" label="密码"><a-input-password v-model:value="editForm.password" /></a-form-item>
        <a-form-item v-if="!editingId" label="管理员">
          <a-switch v-model:checked="editForm.isAdmin" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="resetOpen" title="重置密码" @ok="submitResetPassword" :confirm-loading="submitting">
      <a-form layout="vertical">
        <a-form-item label="新密码"><a-input-password v-model:value="resetPassword" /></a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { changeUserStatus, createUser, pageUsers, resetPassword as resetPasswordApi, updateUser } from '@/api/users'
import type { UserItem } from '@/types/user'

const loading = ref(false)
const submitting = ref(false)
const keyword = ref('')
const rows = ref<UserItem[]>([])
const total = ref(0)
const offset = ref(0)
const size = ref(10)
const editOpen = ref(false)
const resetOpen = ref(false)
const editingId = ref<number | null>(null)
const resetUserId = ref<number | null>(null)
const resetPasswordValue = ref('')

const editForm = reactive({
  username: '',
  email: '',
  nickname: '',
  remark: '',
  password: '',
  isAdmin: false,
})

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username', width: 140 },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 220 },
  { title: '昵称', dataIndex: 'nickname', key: 'nickname', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '管理员', dataIndex: 'isAdmin', key: 'isAdmin', width: 100 },
  { title: '最近登录', dataIndex: 'lastLoginAt', key: 'lastLoginAt', width: 180 },
  { title: '操作', key: 'actions', width: 220 },
]

const pagination = {
  current: 1,
  pageSize: size.value,
  total: total.value,
  showSizeChanger: false,
}

const resetPassword = computed({
  get: () => resetPasswordValue.value,
  set: (value: string) => {
    resetPasswordValue.value = value
  },
})

async function loadUsers() {
  loading.value = true
  try {
    const data = await pageUsers({ offset: offset.value, size: size.value, keyword: keyword.value })
    rows.value = data.data
    total.value = data.total
    pagination.total = data.total
    pagination.current = Math.floor(offset.value / size.value) + 1
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(editForm, { username: '', email: '', nickname: '', remark: '', password: '', isAdmin: false })
  editOpen.value = true
}

function openEdit(record: UserItem) {
  editingId.value = record.id
  Object.assign(editForm, {
    username: record.username,
    email: record.email,
    nickname: record.nickname,
    remark: record.remark,
    password: '',
    isAdmin: record.isAdmin,
  })
  editOpen.value = true
}

function openResetPassword(record: UserItem) {
  resetUserId.value = record.id
  resetPasswordValue.value = ''
  resetOpen.value = true
}

async function submitUser() {
  submitting.value = true
  try {
    if (editingId.value) {
      await updateUser({ id: editingId.value, email: editForm.email, nickname: editForm.nickname, remark: editForm.remark })
      message.success('用户已更新')
    } else {
      await createUser({
        username: editForm.username,
        email: editForm.email,
        nickname: editForm.nickname,
        remark: editForm.remark,
        password: editForm.password,
        isAdmin: editForm.isAdmin,
      })
      message.success('用户已创建')
    }
    editOpen.value = false
    await loadUsers()
  } finally {
    submitting.value = false
  }
}

async function submitResetPassword() {
  if (!resetUserId.value) return
  submitting.value = true
  try {
    await resetPasswordApi({ id: resetUserId.value, password: resetPasswordValue.value })
    message.success('密码已重置')
    resetOpen.value = false
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(record: UserItem) {
  await changeUserStatus({ id: record.id, status: record.status === 'active' ? 'locked' : 'active' })
  message.success('状态已更新')
  await loadUsers()
}

function handleTableChange(page: { current?: number }) {
  offset.value = ((page.current || 1) - 1) * size.value
  loadUsers()
}

onMounted(loadUsers)
</script>
