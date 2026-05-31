<template>
	<Sidebar v-model:collapsed="isSidebarCollapsed" :header="header" :sections="sections">
		<template #footer-items="{ isCollapsed }">
			<DemoDataBanner v-if="!isCollapsed" class="m-2 p-2" />
			<TrialBanner v-if="is_fc_site" :is-sidebar-collapsed="isCollapsed" />
		</template>
	</Sidebar>

	<Settings v-model="showSettingsDialog" />

	<Dialog
		v-model="showLoginToFCDialog"
		:options="{
			title: __('Login to Frappe Cloud?'),
			message: __('Are you sure you want to login to your Frappe Cloud dashboard?'),
			actions: [
				{
					label: __('Confirm'),
					variant: 'solid',
					loading: loggingInToFC,
					onClick() {
						loginToFC()
						showLoginToFCDialog = false
					},
				},
			],
		}"
	/>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { call, Dialog, Sidebar } from 'frappe-ui'
import { TrialBanner } from 'frappe-ui/frappe'
import {
	Book,
	Database,
	DatabaseZap,
	HelpCircle,
	LayoutGrid,
	LogOut,
	MessageCircle,
	SettingsIcon,
	ToggleRight,
} from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { showErrorToast, waitUntil } from '../helpers'
import { confirmDialog } from '../helpers/confirm_dialog'
import useSettings from '../settings/settings'
import Settings from '../settings/Settings.vue'
import session from '../session'
import { __ } from '../translation'
import DemoDataBanner from './DemoDataBanner.vue'
import FrappeCloudIcon from './Icons/FrappeCloudIcon.vue'
// @ts-expect-error
import insightsLogo from '../assets/insights-logo-new.svg'

const isSidebarCollapsed = useStorage('insights:sidebarCollapsed', false)
const showSettingsDialog = ref(false)
const showLoginToFCDialog = ref(false)
const loggingInToFC = ref(false)

const settings = useSettings()

const menuItems = ref([
	{
		label: __('Documentation'),
		icon: HelpCircle,
		onClick: () => window.open('https://docs.frappe.io/insights', '_blank'),
	},
	{
		label: __('Join Telegram Group'),
		icon: MessageCircle,
		onClick: () => window.open('https://t.me/frappeinsights', '_blank'),
	},
	{
		label: __('Log out'),
		icon: LogOut,
		onClick: () =>
			confirmDialog({
				title: __('Log out'),
				message: __('Are you sure you want to log out?'),
				onSuccess: session.logout,
			}),
	},
])

waitUntil(() => session.initialized).then(() => {
	if (session.user.is_admin) {
		menuItems.value.splice(menuItems.value.length - 1, 0, {
			label: __('Switch to Desk'),
			icon: ToggleRight,
			onClick: () => window.open('/app', '_blank'),
		})
	}
})

// @ts-expect-error
const is_fc_site = window.is_fc_site
if (is_fc_site) {
	menuItems.value.splice(menuItems.value.length - 1, 0, {
		label: __('Login to Frappe Cloud'),
		// @ts-expect-error
		icon: FrappeCloudIcon,
		onClick: () => (showLoginToFCDialog.value = true),
	})
}

const header = computed(() => ({
	title: 'Insights',
	subtitle:
		session.user.full_name === 'Administrator'
			? __(session.user.full_name)
			: session.user.full_name,
	logo: insightsLogo,
	menuItems: menuItems.value,
}))

function loginToFC() {
	loggingInToFC.value = true
	call('frappe.integrations.frappe_providers.frappecloud_billing.current_site_info')
		.then((data: any) => {
			if (!data.base_url || !data.site_name) {
				throw new Error('Invalid response')
			}
			window.open(`${data.base_url}/dashboard/sites/${data.site_name}`, '_blank')
		})
		.catch(showErrorToast)
		.finally(() => {
			loggingInToFC.value = false
		})
}

const sections = [
	{
		items: [
			{
				label: __('Dashboards'),
				icon: LayoutGrid,
				to: { name: 'DashboardList' },
			},
			{
				label: __('Workbooks'),
				icon: Book,
				to: { name: 'WorkbookList' },
			},
			{
				label: __('Data Sources'),
				icon: Database,
				to: { name: 'DataSourceList' },
			},
			{
				label: __('Data Store'),
				icon: DatabaseZap,
				to: { name: 'DataStoreList' },
				condition: computed(() => settings.doc.enable_data_store),
			},
			{
				label: __('Settings'),
				icon: SettingsIcon,
				onClick: () => (showSettingsDialog.value = true),
			},
		],
	},
]
</script>
