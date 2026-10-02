<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">异常格保持 ⚠ 标记且不可对调；可走「历史格回洗」显式逐格改写，或保持只读异常</p>
    <div style="display:flex;gap:8px;margin:12px 0">
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>Day {{ d }}</header>
        <div v-for="a in byDay(d)" :key="a.id" class="cell" :class="{ anomaly: a.anomaly }">
          <span class="chip">{{ a.task_title }}</span>
          <span class="chip coral">{{ a.member_name }}</span>
          <span v-if="a.anomaly" class="chip warn" :title="a.anomaly_reasons.join(' ')">
            ⚠ {{ a.anomaly_reasons.join('/') }}
          </span>
          <div v-if="a.anomaly">
            <button v-if="washFor !== a.id" class="ghost mini" @click="openWash(a)">历史格回洗</button>
            <div v-else class="wash-form">
              <select v-model.number="wash.member_id">
                <option :value="a.member_id" v-if="!eligibleMemberIds.includes(a.member_id)">
                  {{ a.member_name }}（原引用，仍不可排）
                </option>
                <option v-for="m in eligibleMembers" :key="m.id" :value="m.id">{{ m.name }}</option>
              </select>
              <select v-model.number="wash.task_id">
                <option :value="a.task_id" v-if="!eligibleTaskIds.includes(a.task_id)">
                  {{ a.task_title }}（原引用，仍不可排）
                </option>
                <option v-for="t in eligibleTasks" :key="t.id" :value="t.id">{{ t.title }}</option>
              </select>
              <button class="mini" @click="doWash(a)">改写此格</button>
              <button class="ghost mini" @click="washFor = 0">保持只读</button>
            </div>
          </div>
        </div>
        <p v-if="!byDay(d).length" class="muted">空</p>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
const assigns = ref([])
const members = ref([])
const tasks = ref([])
const days = [0,1,2,3,4,5,6]
const err = ref('')
const weekId = 1
const washFor = ref(0)
const wash = ref({ member_id: 0, task_id: 0 })
const eligibleMembers = computed(() => members.value.filter(m => m.eligible))
const eligibleTasks = computed(() => tasks.value.filter(t => t.eligible))
const eligibleMemberIds = computed(() => eligibleMembers.value.map(m => m.id))
const eligibleTaskIds = computed(() => eligibleTasks.value.map(t => t.id))
function byDay(d) { return assigns.value.filter(a => a.day === d) }
async function load() {
  err.value = ''
  try {
    const b = await api('/weeks/' + weekId + '/board')
    assigns.value = b.assignments || []
    members.value = await api('/members')
    tasks.value = await api('/tasks')
  } catch (e) { err.value = e.message }
}
async function generate() {
  err.value = ''
  try { await api('/weeks/' + weekId + '/generate', { method: 'POST', body: '{}' }); await load() }
  catch (e) { err.value = e.message }
}
function openWash(a) {
  washFor.value = a.id
  wash.value = { member_id: a.member_id, task_id: a.task_id }
}
async function doWash(a) {
  err.value = ''
  try {
    await api('/assignments/' + a.id + '/wash', { method: 'POST', body: JSON.stringify(wash.value) })
    washFor.value = 0
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
