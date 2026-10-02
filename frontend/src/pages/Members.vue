<template>
  <div>
    <h1 class="brand">成员</h1>
    <p class="muted">dirty / 停用成员照常展示，但生成与对调不会引用；「现行回洗」标 clean 后仅新生成可纳入</p>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="m in rows" :key="m.id">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <span v-if="!m.eligible" class="chip warn">不可排 {{ m.problems.join('/') }}</span>
        <span class="row-actions">
          <button class="ghost" @click="wash(m)">现行回洗</button>
          <button v-if="m.data_quality !== 'dirty'" class="ghost" @click="dirty(m)">标 dirty</button>
        </span>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const name = ref('')
const err = ref('')
async function load() { rows.value = await api('/members') }
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
async function wash(m) {
  err.value = ''
  try {
    await api('/members/' + m.id + '/wash', {
      method: 'POST', body: JSON.stringify({ data_quality: 'clean', active: 1 }),
    })
    await load()
  } catch (e) { err.value = e.message }
}
async function dirty(m) {
  err.value = ''
  try {
    await api('/members/' + m.id, { method: 'PUT', body: JSON.stringify({ data_quality: 'dirty' }) })
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
