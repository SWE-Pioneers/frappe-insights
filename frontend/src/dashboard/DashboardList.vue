<template>
	<header class="sticky top-0 z-10 flex items-center justify-between bg-white px-5 py-2.5">
		<PageBreadcrumbs class="h-7" :items="[{ label: __('Dashboards') }]" />
		<div class="space-x-2.5">
			<Button :label="__('New Dashboard')" variant="solid" @click="showDialog = true">
				<template #prefix>
					<Plus class="h-4 w-4" />
				</template>
			</Button>
		</div>
	</header>
	<div class="flex flex-1 space-y-4 overflow-hidden bg-white px-5 py-2">
		<div
			v-if="dashboards?.list?.length"
			class="flex flex-1 flex-col space-y-6 overflow-y-auto p-1"
		>
			<DashboardsGroup
				v-if="favorites.length > 0"
				:dashboards="favorites"
				:title="__('Favorites')"
			/>
			<DashboardsGroup
				v-if="settings.enable_permissions"
				:dashboards="privates"
				:title="__('Private')"
			/>
			<DashboardsGroup :dashboards="sortedDashboards" :title="__('All')" :enableSearch="true" />
		</div>
		<div v-else class="flex flex-1 flex-col items-center justify-center space-y-1">
			<div class="text-base font-light text-gray-600">
				{{ __("You haven't created any dashboards yet.") }}
			</div>
			<div
				class="cursor-pointer text-sm font-light text-blue-500 hover:underline"
				@click="showDialog = true"
			>
				{{ __('Create a new dashboard') }}
			</div>
		</div>
	</div>

	<Dialog :options="{ title: __('New Dashboard') }" v-model="showDialog">
		<template #body-content>
			<Input
				type="text"
				:label="__('Title')"
				:placeholder="__('Enter a suitable title...')"
				v-model="newDashboardTitle"
			/>
		</template>
		<template #actions>
			<Button
				class="w-full"
				variant="solid"
				@click="createDashboard"
				:loading="dashboards.creating"
			>
				{{ __('Create') }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import PageBreadcrumbs from '@/components/PageBreadcrumbs.vue'
import useDashboards from '@/dashboard/useDashboards'
import settingsStore from '@/stores/settingsStore'
import { updateDocumentTitle } from '@/utils'
import { Plus } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DashboardsGroup from './DashboardListGroup.vue'

const settings = settingsStore().settings

const dashboards = useDashboards()
dashboards.reload()
const sortedDashboards = computed(() => {
	// sort alphabetically
	return dashboards.list.sort((a, b) => a.title.localeCompare(b.title))
})
const favorites = computed(() => {
	return dashboards.list.filter((dashboard) => dashboard.is_favourite)
})
const privates = computed(() => {
	return dashboards.list.filter((dashboard) => dashboard.is_private)
})

const showDialog = ref(false)
const route = useRoute()
if (route.hash == '#new') {
	showDialog.value = true
}

const newDashboardTitle = ref('')
const router = useRouter()

async function createDashboard() {
	const name = await dashboards.create(newDashboardTitle.value)
	showDialog.value = false
	newDashboardTitle.value = ''
	router.push(`/dashboard/${name}`)
}

const pageMeta = ref({ title: __('Dashboards') })
updateDocumentTitle(pageMeta)
</script>
