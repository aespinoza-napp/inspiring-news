# Two alerts, both by email to `alert_email` (none without one):
#
# 1. GET /healthz failing - the deep check: inference, SearXNG, the LLM
#    serving its model, Neo4j (backend/src/services/health.py).
# 2. Web search mostly failing. A search that answers nothing still ends
#    in a verdict (UNVERIFIED) that looks like a judgement, so this is
#    the failure nothing else would report. Read from the backend's
#    /metrics, which the Ops Agent scrapes (deploy/gcp/vm/ops-agent.yaml).
#
# Floci emulates Cloud Monitoring's metrics API only - no uptime checks,
# channels or alert policies - so none of this is created under it.

locals {
  monitor     = var.alert_email != "" && !local.emulated
  uptime_host = var.domain != "" ? var.domain : google_compute_address.vm.address
}

resource "google_monitoring_notification_channel" "email" {
  count = local.monitor ? 1 : 0

  display_name = "${var.name} alerts"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_uptime_check_config" "healthz" {
  count = local.monitor ? 1 : 0

  display_name = "${var.name} /healthz"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/healthz"
    port         = var.domain != "" ? 443 : 80
    use_ssl      = var.domain != ""
    validate_ssl = var.domain != ""
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.uptime_host
    }
  }
}

resource "google_monitoring_alert_policy" "healthz" {
  count = local.monitor ? 1 : 0

  display_name = "${var.name}: a dependency is down"
  combiner     = "OR"

  conditions {
    display_name = "/healthz failing"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
        "resource.type=\"uptime_url\"",
        "metric.label.check_id=\"${google_monitoring_uptime_check_config.healthz[0].uptime_check_id}\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "600s"

      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "GET /healthz on ${local.uptime_host} names the failing dependency in its body. Logs: Cloud Logging, `labels.\"compute.googleapis.com/resource_name\"=\"${var.name}\"`."
  }

  notification_channels = [google_monitoring_notification_channel.email[0].id]
}

resource "google_monitoring_alert_policy" "search_health" {
  count = local.monitor ? 1 : 0

  display_name = "${var.name}: web search is failing"
  combiner     = "OR"

  conditions {
    display_name = "Over half of the last hour's web searches empty or unavailable"

    condition_prometheus_query_language {
      # No searches in the window divides by zero, which is no data, not
      # an alert: an idle stack is not a broken one.
      query               = "sum(increase(inspiring_web_searches_total{result!=\"results\"}[1h])) / sum(increase(inspiring_web_searches_total[1h])) > 0.5"
      duration            = "1800s"
      evaluation_interval = "300s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Claims are coming back UNVERIFIED because search returned nothing, not because of the evidence. SearXNG's engines are being refused from this VM's address: see docs/decisions/retrieval.md and the source probe on /scraper."
  }

  notification_channels = [google_monitoring_notification_channel.email[0].id]
}
