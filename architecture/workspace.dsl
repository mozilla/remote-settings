# TODO:
# What logging is not captured in this diagram
# fluentd, which pushes to bigquery
# Stackdriver?
# Public, Writer,
# Statsd sends metrics to influxdb. Grafana instance
# S3 bucket for lambda(s)?

workspace "Remote Settings" "Remote Settings Service" {

    model {
      firefox = softwaresystem "Firefox" "" "Web Browser" {
        browser = container "Browser" "" {
          remoteSettingsClient = component "Remote Settings Client" ""
          normandyClient = component "Normandy Client" ""
        }
      }
      sentry = softwaresystem "Sentry" "3rd party logging service" "External System, Logging"
      stackdriver = softwaresystem "Stackdriver" "GCP Logging Service" "External System, Logging"
      normandy = softwaresystem "Normandy" "manages recipes of changes to make to Firefox" "External System"
      autograph = softwaresystem "Autograph" "cryptographic signature service that implements Content-Signature, XPI Signing for Firefox web extensions, MAR Signing for Firefox updates, APK V1 Signing for Android, PGP, GPG2 and RSA." "External System"
      megaphone = softwaresystem "Megaphone" "Provides global broadcasts for Firefox" "External System"
      remoteSettings = softwaresystem "Remote Settings" "Manages evergreen settings data in Firefox" {
        remoteSettingsReader = container "Remote Settings Reader" "" "Python, Kinto Server" "Logging"
        remoteSettingsWriter = container "Remote Settings Writer" "" "Python, Kinto Server" "Logging"
        lambdas = container "Remote Settings Lambdas" "" "AWS Lambda" "Logging" {
          # Backport records config
          # https://github.com/mozilla-services/cloudops-deployment/blob/dbb19a8373fe061ba65fe9610845a901a3535943/projects/kinto-lambda/ansible/envs/default.yml
          # arbitrary number of this lambda. How do we represent this?
          backport_records = component "backport_records" "Backport records creations, updates and deletions from one collection to another" "AWS Lambda/ cron job"
          sync_megaphone = component "sync_megaphone" "Read latest timestamp from monitor/changes & updates it in Megaphone if outdated." "AWS Lambda / cron job"
          refresh_signature = component "refresh_signature" "Rotate signature and certificates of collections." "AWS Lambda / cron job"
        }
        database = container "Remote Settings Database" "Storage, cache, and permissions" "Postgres Database" "Database"
        mainCDN = container "Main CDN" "" "AWS Cloudfront" "Database,Logging"
        attachmentsCDN = container "Attachments CDN" "" "AWS Cloudfront" "Database,Logging"
        blocklistCDN = container "Blocklist CDN" "" "AWS Cloudfront" "Database,Logging"
        attachmentsBucket = container "Attachments Bucket" "" "S3 Bucket" "Storage"
        loggingBucket = container "Logging Bucket" "" "S3 Bucket" "Storage,Logging"
        cloudwatch = container "Cloudwatch" "" "AWS Cloudwatch" "Logging"
      }

      normandy -> remoteSettingsWriter "" "HTTPS"
      megaphone -> firefox "Pushes RS data"
      mainCDN -> remoteSettingsReader ""
      attachmentsCDN -> attachmentsBucket ""
      remoteSettingsReader -> database "Reads collections. Read permissions only."
      remoteSettingsWriter -> database "Reads from and writes to" "Postgres Protocol/SSL"
      remoteSettingsWriter -> attachmentsBucket "Writes attachments" "HTTPS"
      remoteSettingsWriter -> autograph "Send serialized collection data to receive content signature" "HTTPS"

      # Logging
      ## Reader / Writer
      remoteSettingsWriter -> sentry "Write logs" "HTTPS" "Logging"
      remoteSettingsReader -> sentry "Write logs" "HTTPS" "Logging"
      remoteSettingsWriter -> stackdriver "Write logs" "HTTPS" "Logging"
      remoteSettingsReader -> stackdriver "Write logs" "HTTPS" "Logging"
      ## lambdas
      lambdas -> sentry "Write logs" "HTTPS" "Logging"
      lambdas -> cloudwatch "Write logs" "HTTPS" "Logging"
      ## CDNs
      mainCDN -> loggingBucket "Write Logs" "HTTPS" "Logging"
      attachmentsCDN -> loggingBucket "Write Logs" "HTTPS" "Logging"
      blocklistCDN -> loggingBucket "Write Logs" "HTTPS" "Logging"

      # Lambdas
      lambdas -> remoteSettingsWriter ""
      sync_megaphone -> mainCDN "GET timestamp from monitor/changes"
      sync_megaphone -> megaphone "PUT broadcast timestamp if outdated"
      refresh_signature -> remoteSettingsWriter "PATCH collections with status=to-refresh"
      backport_records -> remoteSettingsWriter "GET source records, PUT/DELETE destination records"

      live = deploymentEnvironment "Live" {
        deploymentNode "Client Device" {
          firefoxInstance = softwareSystemInstance firefox
        }
        deploymentNode "Sentry" {
          sentryInstance = softwareSystemInstance sentry
        }
        deploymentNode "Google Cloud Platform"{
          tags "Google Cloud Platform - Cloud"
          megaphoneInstance = softwareSystemInstance megaphone
          stackdriverInstance = softwareSystemInstance stackdriver
          softwareSystemInstance normandy
        }
        deploymentNode "Amazon Web Services" {
          tags "Amazon Web Services - Cloud"
          softwareSystemInstance autograph
          route53 = infrastructureNode "Route 53" {
            tags "Amazon Web Services - Route 53"
          }
          deploymentNode "Amazon Cloudfront - Main" {
            tags "Amazon Web Services - CloudFront"
            mainCDNInstance = containerInstance mainCDN
          }
          deploymentNode "Amazon Cloudfront - Attachments" {
            tags "Amazon Web Services - CloudFront"
            attachmentsCDNInstance = containerInstance attachmentsCDN
          }
          deploymentNode "Amazon Cloudfront - Blocklist" {
            tags "Amazon Web Services - CloudFront"
            containerInstance blocklistCDN
          }
          deploymentNode "Amazon S3 Bucket - Attachments" {
            tags "Amazon Web Services - Simple Storage Service S3 Bucket with Objects"
            containerInstance attachmentsBucket
          }
          deploymentNode "Amazon S3 Bucket - Cloudfront Logs" {
            tags "Amazon Web Services - Simple Storage Service S3 Bucket with Objects"
            containerInstance loggingBucket
          }
          deploymentNode "Amazon Virtual Private Cloud"{
            tags "Amazon Web Services - VPC"
            deploymentNode "Amazon EC2 - Writer" {
              tags "Amazon Web Services - EC2"
              remoteSettingsWriterInstance = containerInstance remoteSettingsWriter
            }
            deploymentNode "Amazon EC2 - Reader" {
              tags "Amazon Web Services - EC2"
              containerInstance remoteSettingsReader
            }
            deploymentNode "Amazon RDS" {
              tags "Amazon Web Services - RDS"
              deploymentNode "AWS Postgres" {
                tags "Amazon Web Services - RDS PostgreSQL instance"
                containerInstance database
              }
            }
            deploymentNode "Amazon Lambdas" {
              containerInstance lambdas
            }
          }
          deploymentNode "Amazon Cloudwatch"{
            tags "Amazon Web Services - CloudWatch"
            containerInstance cloudwatch
          }
        }
        firefoxInstance -> route53 "Requests" "HTTPS"
        route53 -> mainCDNInstance "Forwards requests to"
        route53 -> attachmentsCDNInstance "Forwards requests to"
      }
    }

    views {
      component lambdas "RemoteSettingsLambdas"{
        include *
        autolayout lr
      }
      deployment remoteSettings "Live" "CurrentDeployment" {
        include *
        exclude sentry
        exclude stackdriver
      }
      deployment remoteSettings "Live" "CurrentDeploymentLogging" {
        include "element.tag==Logging"
      }
      themes https://static.structurizr.com/themes/amazon-web-services-2020.04.30/theme.json https://static.structurizr.com/themes/google-cloud-platform-v1.5/theme.json default
      styles {
        element "Google Cloud Platform - Cloud" {
          icon https://www.gend.co/hs-fs/hubfs/gcp-logo-cloud.png?width=730&name=gcp-logo-cloud.png
        }
        element "External System" {
          background #999999
          color #ffffff
        }
        element "Database" {
          shape cylinder
        }
        element "Storage" {
          shape folder
        }
        element "Web Browser" {
          shape WebBrowser
        }
      }
    }

}