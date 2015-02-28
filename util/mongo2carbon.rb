#!/usr/bin/env ruby

require 'rubygems'
require 'mongo'
require 'optparse'
require 'socket'

mongo_opts  = [ "localhost", "27017" ]
carbon_opts = [ "monitor",   "2003"  ]
prefix = nil

OptionParser.new do |opts|
  opts.on('-m', '--mongo HOST:PORT', "Mongo host:port to use, default #{mongo_opts.join(":")}") do |o|
    mongo_opts = o.split(":")
  end

  opts.on('-c', '--carbon HOST:PORT', "Carbon host:port to use, default #{carbon_opts.join(":")}") do |o|
    carbon_opts = o.split(":")
  end

  opts.on('-p', '--prefix PREFIX', "Prefix to use for all metrics, default servers.<hostname>.mongodb.<port>") do |o|
    prefix = o
  end
end.parse!

mongo_opts.push({ :slave_ok => true })

if not prefix
  hostname = Socket.gethostname.split('.').first
  prefix = "mongodb.agents.#{hostname}.#{mongo_opts[1]}."
end

# Snippet from http://snippets.dzone.com/posts/show/6776
class Hash
  def flatten_keys(newhash={}, keys=nil)
    self.each do |k, v|
      k = k.to_s
      keys2 = keys ? keys+"."+k : k
      if v.is_a?(Hash)
        v.flatten_keys(newhash, keys2)
      else
        newhash[keys2] = v
      end
    end
    newhash
  end
end

class Carbon
  attr_accessor :data, :prefix, :time

  def initialize(host, port)
    @sock = TCPSocket.open(host, port)
    @data = nil
    @prefix = nil
    @time = nil
  end

  def send(key, value = nil)
    if key.class == Array
      key.each { |k| self.send(k, value) }
      return
    end

    send_key   = @prefix + key
    send_value = value || @data[key]
    send_time  = @time || Time.now.to_i

    @sock.send("#{send_key} #{send_value.to_f} #{send_time}\n", 0)
  end
end

mongo  = Mongo::Connection.new(*mongo_opts)
carbon = Carbon.new(*carbon_opts)

carbon.prefix = prefix
carbon.data = mongo['system'].command({:serverStatus => 1}).flatten_keys
carbon.time = carbon.data['localTime'].to_i

carbon.send([
  "asserts.msg",
  "asserts.regular",
  "asserts.rollovers",
  "asserts.user",
  "asserts.warning",
  "backgroundFlushing.average_ms",
  "backgroundFlushing.flushes",
  "backgroundFlushing.last_finished",
  "backgroundFlushing.last_ms",
  "backgroundFlushing.total_ms",
  "connections.available",
  "connections.current",
  "cursors.clientCursors_size",
  "cursors.timedOut",
  "cursors.totalOpen",
  "dur.commits",
  "dur.commitsInWriteLock",
  "dur.compression",
  "dur.earlyCommits",
  "dur.journaledMB",
  "dur.timeMs.dt",
  "dur.timeMs.prepLogBuffer",
  "dur.timeMs.remapPrivateView",
  "dur.timeMs.writeToDataFiles",
  "dur.timeMs.writeToJournal",
  "dur.writeToDataFilesMB",
  "extra_info.heap_usage_bytes",
  "extra_info.page_faults",
  "globalLock.activeClients.readers",
  "globalLock.activeClients.total",
  "globalLock.activeClients.writers",
  "globalLock.currentQueue.readers",
  "globalLock.currentQueue.total",
  "globalLock.currentQueue.writers",
  "globalLock.lockTime",
  "globalLock.ratio",
  "globalLock.totalTime",
  "indexCounters.btree.accesses",
  "indexCounters.btree.hits",
  "indexCounters.btree.misses",
  "indexCounters.btree.missRatio",
  "indexCounters.btree.resets",
  "mem.bits",
  "mem.mapped",
  "mem.mappedWithJournal",
  "mem.resident",
  "mem.virtual",
  "network.bytesIn",
  "network.bytesOut",
  "network.numRequests",
  "opcounters.command",
  "opcounters.delete",
  "opcounters.getmore",
  "opcounters.insert",
  "opcounters.query",
  "opcountersRepl.command",
  "opcountersRepl.delete",
  "opcountersRepl.getmore",
  "opcountersRepl.insert",
  "opcountersRepl.query",
  "opcountersRepl.update",
  "opcounters.update",
  "process",
  "uptime",
  "uptimeEstimate",
])

carbon.time = nil

mongo.database_names.each do |db_name|
  next if db_name == '*'
  db = mongo[db_name]

  carbon.prefix = prefix + "dbs.#{db_name}."
  carbon.data = db.command({:dbstats => 1})
  carbon.send(["objects", "avgObjSize", "dataSize", "storageSize", "numExtents", "indexes", "indexSize", "fileSize", "nsSizeMB"])

  db.collections.each do |coll|
    carbon.prefix = prefix + "dbs.#{db_name}.collections.#{coll.name}."
    carbon.data = coll.stats.flatten_keys
    carbon.send(["count", "size", "avgObjSize", "storageSize", "numExtents", "nindexes", "lastExtentSize", "paddingFactor", "totalIndexSize"])
    carbon.send(carbon.data.keys.grep(/^indexSizes\./))
  end
end

if replSetStatus = mongo['admin'].command({:replSetGetStatus => 1})
  carbon.time = replSetStatus['date'].to_i
  carbon.prefix = prefix + "replSetStatus.#{replSetStatus['set']}."

  carbon.send('members_count', replSetStatus['members'].count)

  selfStatus = (replSetStatus['members'].select { |m| m['self'] == true }).first

  carbon.prefix += "self."
  carbon.data = selfStatus
  carbon.send(['_id', 'health', 'state'])
  carbon.send('optimeLag', replSetStatus['date'].to_i - selfStatus['optimeDate'].to_i)
end

currentOp = mongo['admin']['$cmd.sys.inprog'].find().first['inprog']
runningTime = currentOp.map { |op| op['secs_running'] }.compact

data = {}
data['count'] = currentOp.count
data['runningTime.avg'] = runningTime.size == 0 ? 0 : runningTime.inject{ |sum, element| sum + element }.to_f / runningTime.size
data['runningTime.min'] = runningTime.min
data['runningTime.max'] = runningTime.max

carbon.prefix = prefix + "currentOp."
carbon.data = data
carbon.send(data.keys)
