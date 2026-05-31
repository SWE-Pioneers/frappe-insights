<script setup lang="ts">
import { Sidebar } from 'frappe-ui'
import { computed } from 'vue'

export type Tab = {
	label: string
	component?: any
	icon?: any
}
export type TabGroup = {
	groupLabel: string
	tabs: Tab[]
}
export type Tabs = Tab[] | TabGroup[]

const props = defineProps<{ title?: string; tabs: Tabs }>()

const activeTab = defineModel<Tab>('activeTab', {
	type: Object,
})

const tabGroups = computed(() => {
	if (!props.tabs.length) return []
	if ('tabs' in props.tabs[0]) return props.tabs as TabGroup[]
	return [{ groupLabel: '', tabs: props.tabs as Tab[] }]
})

const sections = computed(() =>
	tabGroups.value.map((group) => ({
		label: group.groupLabel,
		items: group.tabs.map((tab) => ({
			label: tab.label,
			icon: tab.icon,
			isActive: activeTab.value?.label === tab.label,
			onClick: () => (activeTab.value = tab),
		})),
	})),
)
</script>

<template>
	<div class="flex h-full w-full">
		<Sidebar :sections="sections" disable-collapse>
			<template #header>
				<h1 v-if="props.title" class="px-2 py-2 text-lg font-semibold text-ink-gray-8">
					{{ props.title }}
				</h1>
			</template>
		</Sidebar>
		<div class="flex h-full flex-1 flex-col overflow-hidden">
			<component v-if="activeTab?.component" :is="activeTab.component" />
		</div>
	</div>
</template>
