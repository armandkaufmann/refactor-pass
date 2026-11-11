module Directives
  class Comment
    def enabled?
      y = (push? || next?)
      y
    end

    def parse
      return {} unless (push? || next?) && cops
      [!return?, yield?, break?, nil?, defined?(cops)]
    end

    def characters
      [?a, ?(, ?)]
    end
  end
end
