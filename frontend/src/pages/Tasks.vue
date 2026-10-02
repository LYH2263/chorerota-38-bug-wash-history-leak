<template>
  <div>
    <h1 class="brand">任务</h1>
    <p class="muted">负权 / dirty 任务照常展示，但生成与对调不会引用；「现行回洗」标 clean 并修正权重后仅新生成可纳入</p>
    <form @submit.prevent="add">
      <input v-model="title" placeholder="任务名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="t in rows" :key="t.id">
        <strong>{{ t.title }}</strong>
        <span class="muted"> · 权重 {{ t.weight }} · {{ t.data_quality }}</span>
        <span v-if="!t.eligible" class="chip warn">不可排 {{ t.problems.join('/') }}</span>
        <span class="row-actions">
          <input
            v-if="t.weight <= 0"
            type="number" min="1" style="width:70px;display:inline-block;margin:0 4px"
            v-model.number="fixWeight[t.id]" placeholder="权重" />
          <button class="ghost" @click="wash(t)">现行回洗</button>
          <button v-if="t.data_quality !== 'dirty'" class="ghost" @click="dirty(t)">标 dirty</button>
        </span>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const title = ref('')
const err = ref('')
const fixWeight = ref({})
async function load() {
  rows.value = await api('/tasks')
  for (const t of rows.value) {
    if (t.weight <= 0 && !fixWeight.value[t.id]) fixWeight.value[t.id] = 1
  }
}
async function add() {
  if (!title.value.trim()) return
  await api('/tasks', { method: 'POST', body: JSON.stringify({ title: title.value }) })
  title.value = ''; await load()
}
async function wash(t) {
  err.value = ''
  const body = { data_quality: 'clean' }
  if (t.weight <= 0) body.weight = fixWeight.value[t.id] || 1
  try {
    await api('/tasks/' + t.id + '/wash', { method: 'POST', body: JSON.stringify(body) })
    await load()
  } catch (e) { err.value = e.message }
}
async function dirty(t) {
  err.value = ''
  try {
    await api('/tasks/' + t.id, { method: 'PUT', body: JSON.stringify({ data_quality: 'dirty' }) })
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
